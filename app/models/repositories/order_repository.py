from datetime import date
from typing import Optional

from app.models.enums import DeliveryMethod, EventCategory, OrderStatus, PaymentStatus
from app.models.order import GuestGroup, Order, OrderLine
from app.models.repositories.db import next_ids, query, to_db_time, to_native, write

# Every order with its customer and event type. The WHERE clause goes after this pattern.
MATCH_ORDER = "MATCH (c:Customer)-[:PLACED]->(o:Order)-[:FOR_EVENT]->(e:EventCategory)"
# The order with its guest groups and lines, read in the same query.
ORDER = ("o {.*, customer_id: c.id, event_type: e.value,"
         " guest_groups: [(o)-[:HAS_GUEST_GROUP]->(g:GuestGroup) | g {.*}],"
         " lines: [(o)-[:HAS_LINE]->(l:OrderLine)-[:OF_ITEM]->(f:FoodItem) | l {.*, food_item_id: f.id}]} AS order")
MAX_NUMBER = ("MATCH (o:Order) WHERE o.order_number STARTS WITH $prefix"
              " RETURN max(toInteger(substring(o.order_number, size($prefix)))) AS n")


class OrderRepository:
    def add(self, order: Order) -> Order:
        """Save an order together with its guest groups and lines in one transaction.
        A new order without a number gets the next one, e.g. EM-2026-0007."""
        def create(tx):
            order_number = order.order_number
            if not order_number:
                prefix = f"EM-{order.created_at.year}-"
                order_number = self._format_number(prefix, tx.run(MAX_NUMBER, prefix=prefix).single()["n"])
            [order_id] = next_ids(tx, "Order")
            group_ids = next_ids(tx, "GuestGroup", len(order.guest_groups))
            line_ids = next_ids(tx, "OrderLine", len(order.lines))
            created = tx.run(
                "MATCH (c:Customer {id: $customer_id}), (e:EventCategory {value: $event_type})"
                " CREATE (c)-[:PLACED]->(o:Order {id: $id})-[:FOR_EVENT]->(e) SET o += $props RETURN o",
                customer_id=order.customer_id, event_type=order.event_type.value, id=order_id,
                props={"order_number": order_number, "event_date": order.event_date,
                       "delivery_method": order.delivery_method.value, "delivery_address": order.delivery_address,
                       "status": order.status.value, "payment_status": order.payment_status.value,
                       "created_at": to_db_time(order.created_at)},
            ).single()
            if created is None:
                raise ValueError(f"Unknown customer {order.customer_id}.")
            tx.run("MATCH (o:Order {id: $id}) UNWIND $groups AS g"
                   " CREATE (o)-[:HAS_GUEST_GROUP]->(gg:GuestGroup) SET gg = g",
                   id=order_id, groups=[{"id": gid, "label": g.label, "guest_count": g.guest_count,
                                          "diet_notes": g.diet_notes}
                                         for gid, g in zip(group_ids, order.guest_groups)]).consume()
            count = tx.run("MATCH (o:Order {id: $id}) UNWIND $lines AS l"
                           " MATCH (f:FoodItem {id: l.food_item_id})"
                           " CREATE (o)-[:HAS_LINE]->(:OrderLine {id: l.id, quantity: l.quantity,"
                           " unit_price_nok: l.unit_price_nok})-[:OF_ITEM]->(f) RETURN count(*) AS n",
                           id=order_id, lines=[{"id": lid, "food_item_id": l.food_item_id, "quantity": l.quantity,
                                                "unit_price_nok": l.unit_price_nok}
                                               for lid, l in zip(line_ids, order.lines)]).single()["n"]
            if count != len(order.lines):
                raise ValueError("An order line refers to an unknown food item.")
            return order_number, order_id, group_ids, line_ids

        order.order_number, order.id, group_ids, line_ids = write(create)
        for group, group_id in zip(order.guest_groups, group_ids):
            group.id, group.order_id = group_id, order.id
        for line, line_id in zip(order.lines, line_ids):
            line.id, line.order_id = line_id, order.id
        return order

    def get(self, order_id: int) -> Optional[Order]:
        records = query(f"{MATCH_ORDER} WHERE o.id = $id RETURN {ORDER}", id=order_id)
        return self._to_order(records[0]["order"]) if records else None

    def next_order_number(self, year: Optional[int] = None) -> str:
        prefix = f"EM-{year or date.today().year}-"
        return self._format_number(prefix, query(MAX_NUMBER, prefix=prefix)[0]["n"])

    def search(self, status: Optional[OrderStatus] = None, date_from: Optional[date] = None,
               date_to: Optional[date] = None, customer_id: Optional[int] = None,
               newest_first: bool = False) -> list[Order]:
        """Orders matching all given filters. Event dates are inclusive at both ends."""
        conditions, params = [], {}
        if status is not None:
            conditions.append("o.status = $status")
            params["status"] = status.value
        if date_from is not None:
            conditions.append("o.event_date >= $date_from")
            params["date_from"] = date_from
        if date_to is not None:
            conditions.append("o.event_date <= $date_to")
            params["date_to"] = date_to
        if customer_id is not None:
            conditions.append("c.id = $customer_id")
            params["customer_id"] = customer_id
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        direction = "DESC" if newest_first else "ASC"
        records = query(f"{MATCH_ORDER}{where} RETURN {ORDER} ORDER BY o.event_date {direction}, o.id {direction}",
                        **params)
        return [self._to_order(r["order"]) for r in records]

    def list_all(self) -> list[Order]:
        return self.search()

    def list_by_customer(self, customer_id: int) -> list[Order]:
        return self.search(customer_id=customer_id, newest_first=True)

    def count_by_status(self, status: OrderStatus) -> int:
        return query("MATCH (o:Order {status: $status}) RETURN count(o) AS n", status=status.value)[0]["n"]

    def update_status(self, order: Order) -> None:
        """Persist status and payment status. Transition rules are checked in Order.change_status."""
        query("MATCH (o:Order {id: $id}) SET o.status = $status, o.payment_status = $payment_status",
              id=order.id, status=order.status.value, payment_status=order.payment_status.value)

    @staticmethod
    def _format_number(prefix: str, highest: Optional[int]) -> str:
        return f"{prefix}{(highest or 0) + 1:04d}"

    @staticmethod
    def _to_order(data) -> Order:
        groups = [
            GuestGroup(id=g["id"], order_id=data["id"], label=g.get("label"),
                       guest_count=g["guest_count"], diet_notes=g.get("diet_notes"))
            for g in sorted(data["guest_groups"], key=lambda g: g["id"])
        ]
        lines = [
            OrderLine(id=l["id"], order_id=data["id"], food_item_id=l["food_item_id"],
                      quantity=l["quantity"], unit_price_nok=l["unit_price_nok"])
            for l in sorted(data["lines"], key=lambda l: l["id"])
        ]
        return Order(
            id=data["id"],
            order_number=data["order_number"],
            customer_id=data["customer_id"],
            event_type=EventCategory(data["event_type"]),
            event_date=to_native(data["event_date"]),
            delivery_method=DeliveryMethod(data["delivery_method"]),
            delivery_address=data.get("delivery_address"),
            status=OrderStatus(data["status"]),
            payment_status=PaymentStatus(data["payment_status"]),
            created_at=to_native(data["created_at"]),
            guest_groups=groups,
            lines=lines,
        )
