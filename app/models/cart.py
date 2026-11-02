from dataclasses import dataclass, field
from typing import Optional

from app.models.errors import CartError
from app.models.food_item import FoodItem


@dataclass
class CartLine:
    food_item: FoodItem
    quantity: int  # portions

    @property
    def line_total_nok(self) -> int:
        return self.quantity * self.food_item.price_nok


@dataclass
class Cart:
    """The customer's cart before ordering: food item id -> number of portions.

    Prices are never stored here; they are looked up from the current food items,
    which is why the total shown to the customer is an estimate until the order is placed.
    """
    quantities: dict[int, int] = field(default_factory=dict)

    MAX_QUANTITY = 1000

    @classmethod
    def validate_quantity(cls, item: FoodItem, quantity: int) -> Optional[str]:
        if not item.published:
            return f"{item.name_en} is no longer on the menu."
        if quantity < item.min_order_quantity:
            return (f"{item.name_en}: the minimum order is {item.min_order_quantity} portions "
                    f"(you chose {quantity}).")
        if quantity > cls.MAX_QUANTITY:
            return f"{item.name_en}: at most {cls.MAX_QUANTITY} portions can be ordered online."
        return None

    def add(self, item: FoodItem, quantity: int) -> None:
        """Add portions; if the dish is already in the cart, the quantities are added together."""
        new_quantity = self.quantities.get(item.id, 0) + quantity
        error = self.validate_quantity(item, new_quantity)
        if error:
            raise CartError(error)
        self.quantities[item.id] = new_quantity

    def set_quantity(self, item: FoodItem, quantity: int) -> None:
        """Change a line. Quantity 0 removes it."""
        if quantity == 0:
            self.remove(item.id)
            return
        error = self.validate_quantity(item, quantity)
        if error:
            raise CartError(error)
        self.quantities[item.id] = quantity

    def remove(self, item_id: int) -> None:
        self.quantities.pop(item_id, None)

    def lines(self, items_by_id: dict[int, FoodItem]) -> tuple[list[CartLine], list[str]]:
        """Build lines from the current food items. Dishes that were deleted or unpublished
        are dropped from the cart; their names are returned so the customer can be told."""
        lines, removed = [], []
        for item_id, quantity in list(self.quantities.items()):
            item = items_by_id.get(item_id)
            if item is None or not item.published:
                removed.append(item.name_en if item else "A dish that is no longer available")
                self.remove(item_id)
            else:
                lines.append(CartLine(item, quantity))
        lines.sort(key=lambda line: line.food_item.name_en)
        return lines, removed

    @staticmethod
    def total_nok(lines: list[CartLine]) -> int:
        return sum(line.line_total_nok for line in lines)

    @property
    def item_count(self) -> int:
        """Number of different dishes in the cart."""
        return len(self.quantities)

    @property
    def is_empty(self) -> bool:
        return not self.quantities
