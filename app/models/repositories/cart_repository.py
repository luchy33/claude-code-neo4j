"""Cart storage. The only code that reads or writes the cart.

Carts are (:Cart)-[:HAS_ITEM {quantity}]->(:FoodItem) in Neo4j and hold only item ids and quantities.
A logged-in customer's cart hangs off (:Customer)-[:HAS_CART]->, so it is kept across logins and devices.
A guest's cart is found by a random token in the session, and that token never opens a customer's cart.
"""
import secrets
from datetime import datetime, timedelta

from flask import session

from app.models.cart import Cart
from app.models.repositories.db import query, to_db_time, write

TOKEN_KEY = "cart_token"
GUEST_CART_LIFETIME = timedelta(days=30)


class CartRepository:
    def load(self) -> Cart:
        match, params = self._match()
        if match is None:
            return Cart()
        records = query(f"{match} MATCH (c)-[h:HAS_ITEM]->(f:FoodItem)"
                        " RETURN f.id AS item_id, h.quantity AS quantity", **params)
        return Cart({r["item_id"]: r["quantity"] for r in records if r["quantity"] > 0})

    def save(self, cart: Cart) -> None:
        if not cart.quantities:
            self.clear()
            return
        now = to_db_time(datetime.now())
        customer_id = session.get("customer_id")
        if customer_id is not None:
            create = ("MATCH (cu:Customer {id: $customer_id}) MERGE (cu)-[:HAS_CART]->(c:Cart)"
                      " ON CREATE SET c.token = $token")
            params = {"customer_id": customer_id, "token": secrets.token_hex(16)}
        else:
            if TOKEN_KEY not in session:
                session[TOKEN_KEY] = secrets.token_hex(16)
            create = "MERGE (c:Cart {token: $token})"
            params = {"token": session[TOKEN_KEY]}
        items = [{"id": item_id, "quantity": quantity} for item_id, quantity in cart.quantities.items()]

        def replace_items(tx):
            tx.run(f"{create} SET c.updated_at = $now WITH c"
                   " OPTIONAL MATCH (c)-[h:HAS_ITEM]->() DELETE h WITH DISTINCT c"
                   " UNWIND $items AS item MATCH (f:FoodItem {id: item.id})"
                   " MERGE (c)-[h:HAS_ITEM]->(f) SET h.quantity = item.quantity",
                   now=now, items=items, **params).consume()
            tx.run("MATCH (c:Cart) WHERE c.updated_at < $cutoff AND NOT (:Customer)-[:HAS_CART]->(c)"
                   " DETACH DELETE c", cutoff=now - GUEST_CART_LIFETIME).consume()

        write(replace_items)

    def clear(self) -> None:
        match, params = self._match()
        if match is not None:
            query(f"{match} DETACH DELETE c", **params)
        session.pop(TOKEN_KEY, None)

    def merge_into_customer(self, guest_cart: Cart) -> None:
        """After login: add the guest's dishes to the customer's saved cart.
        For a dish in both, the guest's quantity wins because it is the latest choice."""
        if guest_cart.quantities:
            saved = self.load()
            self.save(Cart({**saved.quantities, **guest_cart.quantities}))

    @staticmethod
    def _match():
        """MATCH clause binding `c` to the current cart, or None if this visitor has none yet."""
        customer_id = session.get("customer_id")
        if customer_id is not None:
            return "MATCH (:Customer {id: $customer_id})-[:HAS_CART]->(c:Cart)", {"customer_id": customer_id}
        if TOKEN_KEY in session:
            return ("MATCH (c:Cart {token: $token}) WHERE NOT (:Customer)-[:HAS_CART]->(c)",
                    {"token": session[TOKEN_KEY]})
        return None, {}
