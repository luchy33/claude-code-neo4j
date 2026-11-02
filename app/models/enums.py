from enum import Enum


class LabelledEnum(str, Enum):
    """String enum whose values are stored in the database and shown via `label`."""

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").capitalize()


class OrderStatus(LabelledEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    IN_PREPARATION = "in_preparation"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PaymentStatus(LabelledEnum):
    NOT_PAID = "not_paid"
    DEPOSIT_PAID = "deposit_paid"
    INVOICED = "invoiced"
    PAID = "paid"


class EventCategory(LabelledEnum):
    BIRTHDAY = "birthday"
    CONFIRMATION = "confirmation"
    WEDDING = "wedding"
    CONFERENCE = "conference"
    CHRISTMAS_PARTY = "christmas_party"
    LUNCH_MEETING = "lunch_meeting"
    OTHER = "other"

    @property
    def label(self) -> str:
        if self is EventCategory.CHRISTMAS_PARTY:
            return "Christmas party (julebord)"
        return super().label


class Allergen(LabelledEnum):
    """The 14 allergens that must be labelled under EU/EEA food rules."""
    GLUTEN = "gluten"
    CRUSTACEANS = "crustaceans"
    EGGS = "eggs"
    FISH = "fish"
    PEANUTS = "peanuts"
    SOYBEANS = "soybeans"
    MILK = "milk"
    NUTS = "nuts"
    CELERY = "celery"
    MUSTARD = "mustard"
    SESAME = "sesame"
    SULPHITES = "sulphites"
    LUPIN = "lupin"
    MOLLUSCS = "molluscs"


class DietaryLabel(LabelledEnum):
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    LACTOSE_FREE = "lactose_free"


class DeliveryMethod(LabelledEnum):
    DELIVERY = "delivery"
    PICK_UP = "pick_up"
