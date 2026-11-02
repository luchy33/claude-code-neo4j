from datetime import date, timedelta

import pytest

from app.models import (CartLine, DeliveryMethod, EventCategory, FoodItem, GuestGroup, Order, OrderStatus)

TODAY = date(2026, 10, 27)


def soup(price=189):
    return FoodItem(id=1, name_en="Fish soup", name_no="Fiskesuppe", price_nok=price,
                    categories={EventCategory.CONFERENCE}, min_order_quantity=10)


def new_order(**changes):
    details = dict(event_type=EventCategory.CONFERENCE, event_date=TODAY + timedelta(days=7),
                   delivery_method=DeliveryMethod.DELIVERY, delivery_address="Testgaten 1, Bergen")
    groups = changes.pop("guest_groups", [GuestGroup(12, "Main group")])
    lines = changes.pop("cart_lines", [CartLine(soup(), 12)])
    return Order.from_cart(7, lines, groups, **{**details, **changes})


def test_valid_order_has_no_errors():
    assert new_order().validate(TODAY) == []


def test_from_cart_copies_todays_price():
    item = soup(price=189)
    order = Order.from_cart(7, [CartLine(item, 12)], [GuestGroup(12)], event_type=EventCategory.OTHER,
                            event_date=TODAY, delivery_method=DeliveryMethod.PICK_UP)
    item.price_nok = 250  # the menu price changes later

    assert order.lines[0].unit_price_nok == 189
    assert order.total_nok == 12 * 189
    assert order.customer_id == 7 and order.status == OrderStatus.SUBMITTED and order.order_number == ""


@pytest.mark.parametrize("changes, message", [
    ({"cart_lines": []}, "cart is empty"),
    ({"event_date": TODAY}, "event date must be"),
    ({"event_date": TODAY - timedelta(days=3)}, "event date must be"),
    ({"guest_groups": []}, "at least one guest group"),
    ({"guest_groups": [GuestGroup(0, "Kids")]}, "Kids: the number of guests"),
    ({"guest_groups": [GuestGroup(5000)]}, "between 1 and 2000"),
    ({"guest_groups": [GuestGroup(3, diet_notes="x" * 501)]}, "under 500 characters"),
    ({"delivery_address": "  "}, "delivery address"),
])
def test_validate_reports_each_error(changes, message):
    errors = new_order(**changes).validate(TODAY)

    assert len(errors) == 1 and message in errors[0]


def test_pick_up_needs_no_address():
    order = new_order(delivery_method=DeliveryMethod.PICK_UP, delivery_address=None)

    assert order.validate(TODAY) == []


def test_tomorrow_is_the_earliest_date():
    assert new_order(event_date=TODAY + timedelta(days=1)).validate(TODAY) == []


@pytest.mark.parametrize("status, expected", [
    (OrderStatus.SUBMITTED, [OrderStatus.APPROVED, OrderStatus.REJECTED, OrderStatus.CANCELLED]),
    (OrderStatus.APPROVED, [OrderStatus.IN_PREPARATION, OrderStatus.CANCELLED]),
    (OrderStatus.IN_PREPARATION, [OrderStatus.DELIVERED]),
    (OrderStatus.DELIVERED, []),
    (OrderStatus.REJECTED, []),
    (OrderStatus.CANCELLED, []),
])
def test_next_statuses(status, expected):
    order = new_order(status=status)

    assert order.next_statuses == expected
    assert order.is_final == (expected == [])


def test_illegal_status_change_is_refused():
    order = new_order()
    with pytest.raises(ValueError, match="submitted cannot be changed to delivered"):
        order.change_status(OrderStatus.DELIVERED)
    assert order.status == OrderStatus.SUBMITTED
