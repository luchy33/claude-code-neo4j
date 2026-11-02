from datetime import date, datetime
from typing import Optional

from app.models.enums import DeliveryMethod, EventCategory, OrderStatus, PaymentStatus
from app.models.order import GuestGroup, Order, OrderLine
from app.models.repositories.db import get_db


class OrderRepository:
    def add(self, order: Order) -> Order:
        """Save an order together with its guest groups and lines in one transaction.
        A new order without a number gets the next one, e.g. EM-2026-0007."""
        db = get_db()
        with db:
            if not order.order_number:
                order.order_number = self.next_order_number(order.created_at.year)
            cur = db.execute(
                "INSERT INTO customer_order (order_number, customer_id, event_type, event_date,"
                " delivery_method, delivery_address, status, payment_status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (order.order_number, order.customer_id, order.event_type.value,
                 order.event_date.isoformat(), order.delivery_method.value, order.delivery_address,
                 order.status.value, order.payment_status.value,
                 order.created_at.isoformat(timespec="seconds")),
            )
            order.id = cur.lastrowid
            for group in order.guest_groups:
                cur = db.execute(
                    "INSERT INTO guest_group (order_id, label, guest_count, diet_notes) VALUES (?, ?, ?, ?)",
                    (order.id, group.label, group.guest_count, group.diet_notes),
                )
                group.id, group.order_id = cur.lastrowid, order.id
            for line in order.lines:
                cur = db.execute(
                    "INSERT INTO order_line (order_id, food_item_id, quantity, unit_price_nok) VALUES (?, ?, ?, ?)",
                    (order.id, line.food_item_id, line.quantity, line.unit_price_nok),
                )
                line.id, line.order_id = cur.lastrowid, order.id
        return order

    def get(self, order_id: int) -> Optional[Order]:
        row = get_db().execute("SELECT * FROM customer_order WHERE id = ?", (order_id,)).fetchone()
        return self._to_order(row) if row else None

    def next_order_number(self, year: Optional[int] = None) -> str:
        year = year or date.today().year
        prefix = f"EM-{year}-"
        row = get_db().execute(
            "SELECT MAX(CAST(SUBSTR(order_number, ?) AS INTEGER)) FROM customer_order WHERE order_number LIKE ?",
            (len(prefix) + 1, prefix + "%"),
        ).fetchone()
        return f"{prefix}{(row[0] or 0) + 1:04d}"

    def search(self, status: Optional[OrderStatus] = None, date_from: Optional[date] = None,
               date_to: Optional[date] = None, customer_id: Optional[int] = None,
               newest_first: bool = False) -> list[Order]:
        """Orders matching all given filters. Event dates are inclusive at both ends."""
        conditions, params = [], []
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if date_from is not None:
            conditions.append("event_date >= ?")
            params.append(date_from.isoformat())
        if date_to is not None:
            conditions.append("event_date <= ?")
            params.append(date_to.isoformat())
        if customer_id is not None:
            conditions.append("customer_id = ?")
            params.append(customer_id)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        direction = "DESC" if newest_first else "ASC"
        rows = get_db().execute(
            f"SELECT * FROM customer_order{where} ORDER BY event_date {direction}, id {direction}", params
        ).fetchall()
        return [self._to_order(r) for r in rows]

    def list_all(self) -> list[Order]:
        return self.search()

    def list_by_customer(self, customer_id: int) -> list[Order]:
        return self.search(customer_id=customer_id, newest_first=True)

    def count_by_status(self, status: OrderStatus) -> int:
        return get_db().execute("SELECT COUNT(*) FROM customer_order WHERE status = ?", (status.value,)).fetchone()[0]

    def update_status(self, order: Order) -> None:
        """Persist status and payment status. Transition rules are checked in Order.change_status."""
        db = get_db()
        db.execute(
            "UPDATE customer_order SET status = ?, payment_status = ? WHERE id = ?",
            (order.status.value, order.payment_status.value, order.id),
        )
        db.commit()

    def _to_order(self, row) -> Order:
        db = get_db()
        groups = [
            GuestGroup(id=g["id"], order_id=g["order_id"], label=g["label"],
                       guest_count=g["guest_count"], diet_notes=g["diet_notes"])
            for g in db.execute("SELECT * FROM guest_group WHERE order_id = ? ORDER BY id", (row["id"],))
        ]
        lines = [
            OrderLine(id=l["id"], order_id=l["order_id"], food_item_id=l["food_item_id"],
                      quantity=l["quantity"], unit_price_nok=l["unit_price_nok"])
            for l in db.execute("SELECT * FROM order_line WHERE order_id = ? ORDER BY id", (row["id"],))
        ]
        return Order(
            id=row["id"],
            order_number=row["order_number"],
            customer_id=row["customer_id"],
            event_type=EventCategory(row["event_type"]),
            event_date=date.fromisoformat(row["event_date"]),
            delivery_method=DeliveryMethod(row["delivery_method"]),
            delivery_address=row["delivery_address"],
            status=OrderStatus(row["status"]),
            payment_status=PaymentStatus(row["payment_status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            guest_groups=groups,
            lines=lines,
        )
