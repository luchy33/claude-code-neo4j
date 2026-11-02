from datetime import date, timedelta

import pytest

from app.models import OrderStatus, PaymentStatus
from app.models.repositories import FoodItemRepository, OrderRepository
from tests.conftest import login

FUTURE = (date.today() + timedelta(days=14)).isoformat()
CHECKOUT = {
    "event_type": "conference", "event_date": FUTURE, "delivery_method": "delivery",
    "delivery_address": "Testgaten 1, 5003 Bergen",
    "group_label-0": "Main group", "group_count-0": "10", "group_notes-0": "",
    "group_label-1": "Gluten free", "group_count-1": "2", "group_notes-1": "2 guests: gluten free",
    "group_label-2": "", "group_count-2": "", "group_notes-2": "",
}


@pytest.fixture
def ready(client, customer, food_item):
    """Logged-in customer with 12 × Fish soup in the cart."""
    client.post("/cart/add", data={"food_item_id": food_item.id, "quantity": 12})
    login(client, customer.email)
    return client


def test_checkout_requires_login(client, food_item):
    client.post("/cart/add", data={"food_item_id": food_item.id, "quantity": 12})

    response = client.get("/checkout")
    assert response.status_code == 302 and "/account/login?next=/checkout" in response.headers["Location"]


def test_empty_cart_goes_back_to_cart(client, customer):
    login(client, customer.email)

    response = client.get("/checkout")
    assert response.headers["Location"].endswith("/cart")


def test_checkout_page_shows_form_and_cart(ready):
    html = ready.get("/checkout").get_data(as_text=True)

    assert "12 × Fish soup" in html and "2268 NOK" in html
    assert 'name="group_count-0"' in html and "don't write guests' names" in html


def test_successful_checkout(ready, app, customer):
    response = ready.post("/checkout", data=CHECKOUT)

    assert response.status_code == 302 and "/account/orders/" in response.headers["Location"]
    with app.app_context():
        [order] = OrderRepository().list_by_customer(customer.id)
    assert order.status == OrderStatus.SUBMITTED and order.payment_status == PaymentStatus.NOT_PAID
    assert order.event_date.isoformat() == FUTURE and order.delivery_address == "Testgaten 1, 5003 Bergen"
    assert [(g.label, g.guest_count, g.diet_notes) for g in order.guest_groups] == [
        ("Main group", 10, None), ("Gluten free", 2, "2 guests: gluten free")]  # empty row ignored
    assert [(l.quantity, l.unit_price_nok) for l in order.lines] == [(12, 189)]

    page = ready.get(response.headers["Location"]).get_data(as_text=True)
    assert f"Order {order.order_number} was sent" in page and "Submitted" in page
    assert "Cart (0)" in page


@pytest.mark.parametrize("changes, message", [
    ({"event_date": date.today().isoformat()}, "event date must be"),
    ({"event_date": ""}, "Choose the date"),
    ({"event_type": ""}, "Choose the kind of event"),
    ({"delivery_address": ""}, "delivery address"),
    ({"group_label-0": "", "group_count-0": "", "group_label-1": "", "group_count-1": "", "group_notes-1": ""},
     "at least one guest group"),
    ({"group_count-0": "ten"}, "whole number"),
])
def test_checkout_errors_keep_input(ready, app, customer, changes, message):
    response = ready.post("/checkout", data={**CHECKOUT, **changes})

    html = response.get_data(as_text=True)
    assert response.status_code == 400 and message in html
    if "group_notes-1" not in changes:
        assert "2 guests: gluten free" in html  # what the customer typed is kept
    with app.app_context():
        assert OrderRepository().list_by_customer(customer.id) == []
    assert "Cart (1)" in html  # cart is kept


def test_raised_minimum_blocks_checkout(ready, app, customer, food_item):
    with app.app_context():
        food_item.min_order_quantity = 20
        FoodItemRepository().update(food_item)

    response = ready.post("/checkout", data=CHECKOUT)

    assert response.status_code == 400
    assert "minimum order is 20 portions" in response.get_data(as_text=True)
    with app.app_context():
        assert OrderRepository().list_by_customer(customer.id) == []


def test_extra_guest_rows_are_read(ready, app, customer):
    data = {**CHECKOUT, "group_label-5": "Vegans", "group_count-5": "4", "group_notes-5": "vegan"}
    ready.post("/checkout", data=data)

    with app.app_context():
        [order] = OrderRepository().list_by_customer(customer.id)
    assert order.guest_count == 16 and order.guest_groups[-1].label == "Vegans"
