from dataclasses import dataclass, field
from typing import Optional

from app.models.enums import Allergen, DietaryLabel, EventCategory


@dataclass
class FoodItem:
    """A dish Ekte Mat caters ("Dish" in the Lab 7 domain model). Price in NOK per portion."""
    name_en: str
    name_no: str
    price_nok: int
    categories: set[EventCategory] = field(default_factory=set)
    description: str = ""
    min_order_quantity: int = 1
    allergens: set[Allergen] = field(default_factory=set)
    dietary_labels: set[DietaryLabel] = field(default_factory=set)
    image_filename: Optional[str] = None
    published: bool = True
    id: Optional[int] = None

    def validate(self) -> list[str]:
        errors = []
        if not self.name_en.strip():
            errors.append("English name is required.")
        if not self.name_no.strip():
            errors.append("Norwegian name is required.")
        if self.price_nok < 0:
            errors.append("Price cannot be negative.")
        if self.min_order_quantity < 1:
            errors.append("Minimum order quantity must be at least 1.")
        if not self.categories:
            errors.append("Choose at least one event category.")
        return errors

    def sorted_allergens(self) -> list[Allergen]:
        return sorted(self.allergens, key=lambda a: a.value)

    def sorted_dietary_labels(self) -> list[DietaryLabel]:
        return sorted(self.dietary_labels, key=lambda d: d.value)
