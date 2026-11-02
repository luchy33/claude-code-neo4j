"""Cart storage. The only code that reads or writes the cart.

The cart lives in the signed Flask session cookie and holds only item ids and quantities,
so a database or Neo4j cart can replace this class later without changing the controllers.
"""
from flask import session

from app.models.cart import Cart

SESSION_KEY = "cart"


class SessionCartRepository:
    def load(self) -> Cart:
        quantities = {}
        for key, value in (session.get(SESSION_KEY) or {}).items():
            try:
                item_id, quantity = int(key), int(value)
            except (TypeError, ValueError):
                continue  # ignore broken entries instead of failing the page
            if quantity > 0:
                quantities[item_id] = quantity
        return Cart(quantities)

    def save(self, cart: Cart) -> None:
        session[SESSION_KEY] = {str(item_id): quantity for item_id, quantity in cart.quantities.items()}

    def clear(self) -> None:
        session.pop(SESSION_KEY, None)
