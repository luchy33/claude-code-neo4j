from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from app.models.enums import DeliveryMethod, EventCategory, OrderStatus, PaymentStatus


@dataclass
class GuestGroup:
    guest_count: int
    label: Optional[str] = None
    diet_notes: Optional[str] = None
    id: Optional[int] = None
    order_id: Optional[int] = None


@dataclass
class OrderLine:
    food_item_id: int
    quantity: int
    unit_price_nok: int  # copied from the food item when the order is placed
    id: Optional[int] = None
    order_id: Optional[int] = None

    @property
    def total_nok(self) -> int:
        return self.quantity * self.unit_price_nok


@dataclass
class Order:
    order_number: str
    customer_id: int
    event_type: EventCategory
    event_date: date
    delivery_method: DeliveryMethod
    delivery_address: Optional[str] = None
    status: OrderStatus = OrderStatus.SUBMITTED
    payment_status: PaymentStatus = PaymentStatus.NOT_PAID
    created_at: datetime = field(default_factory=datetime.now)
    guest_groups: list[GuestGroup] = field(default_factory=list)
    lines: list[OrderLine] = field(default_factory=list)
    id: Optional[int] = None

    MIN_DAYS_AHEAD = 1          # the event must be at least tomorrow
    MAX_GUESTS_PER_GROUP = 2000
    MAX_NOTES_LENGTH = 500

    ALLOWED_TRANSITIONS = {
        OrderStatus.SUBMITTED: {OrderStatus.APPROVED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
        OrderStatus.APPROVED: {OrderStatus.IN_PREPARATION, OrderStatus.CANCELLED},
        OrderStatus.IN_PREPARATION: {OrderStatus.DELIVERED},
        OrderStatus.DELIVERED: set(),
        OrderStatus.REJECTED: set(),
        OrderStatus.CANCELLED: set(),
    }

    # Fixed order for buttons in the admin panel (forward first, then reject/cancel).
    STATUS_ORDER = [OrderStatus.APPROVED, OrderStatus.IN_PREPARATION, OrderStatus.DELIVERED,
                    OrderStatus.REJECTED, OrderStatus.CANCELLED]

    @classmethod
    def from_cart(cls, customer_id: int, cart_lines, guest_groups: list[GuestGroup], **details) -> "Order":
        """Build a new order from the cart. Today's prices are copied into the order lines,
        so the order total never changes when the menu prices change later."""
        lines = [OrderLine(line.food_item.id, line.quantity, line.food_item.price_nok) for line in cart_lines]
        return cls(order_number="", customer_id=customer_id, guest_groups=guest_groups, lines=lines, **details)

    def validate(self, today: date) -> list[str]:
        errors = []
        if not self.lines:
            errors.append("Your cart is empty.")
        earliest = today + timedelta(days=self.MIN_DAYS_AHEAD)
        if self.event_date < earliest:
            errors.append(f"The event date must be {earliest.strftime('%d.%m.%Y')} or later.")
        if not self.guest_groups:
            errors.append("Add at least one guest group with the number of guests.")
        for number, group in enumerate(self.guest_groups, start=1):
            name = group.label or f"Guest group {number}"
            if not 1 <= group.guest_count <= self.MAX_GUESTS_PER_GROUP:
                errors.append(f"{name}: the number of guests must be between 1 and {self.MAX_GUESTS_PER_GROUP}.")
            if group.diet_notes and len(group.diet_notes) > self.MAX_NOTES_LENGTH:
                errors.append(f"{name}: keep the allergy and diet notes under {self.MAX_NOTES_LENGTH} characters.")
        if self.delivery_method == DeliveryMethod.DELIVERY and not (self.delivery_address or "").strip():
            errors.append("Enter a delivery address, or choose pick-up.")
        return errors

    @property
    def next_statuses(self) -> list[OrderStatus]:
        allowed = self.ALLOWED_TRANSITIONS[self.status]
        return [status for status in self.STATUS_ORDER if status in allowed]

    @property
    def is_final(self) -> bool:
        return not self.ALLOWED_TRANSITIONS[self.status]

    def can_change_status(self, new_status: OrderStatus) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS[self.status]

    def change_status(self, new_status: OrderStatus) -> None:
        if not self.can_change_status(new_status):
            raise ValueError(f"An order that is {self.status.label.lower()} cannot be changed to "
                             f"{new_status.label.lower()}.")
        self.status = new_status

    @property
    def total_nok(self) -> int:
        return sum(line.total_nok for line in self.lines)

    @property
    def guest_count(self) -> int:
        return sum(group.guest_count for group in self.guest_groups)
