import re

import pytest

from app import create_app
from app.models import EventCategory, FoodItem
from app.models.repositories import FoodItemRepository
from app.models.repositories.db import init_db
from config import TestConfig
from tests.conftest import login


@pytest.fixture
def cake(app):
    with app.app_context():
        return FoodItemRepository().add(FoodItem(
            name_en="Coffee and cake", name_no="Kaffe og kake", price_nok=85,
            categories={EventCategory.BIRTHDAY, EventCategory.CONFERENCE}, min_order_quantity=5))


def add(client, item, quantity, section="lunch_meeting"):
    return client.post("/cart/add", data={"food_item_id": item.id, "quantity": quantity, "section": section})


def cart_page(client):
    return client.get("/cart").get_data(as_text=True)


def test_card_has_add_to_cart_form_starting_at_minimum(client, food_item):
    html = client.get("/").get_data(as_text=True)

    assert 'action="/cart/add"' in html
    assert f'id="item-lunch_meeting-{food_item.id}"' in html
    assert 'value="10" min="10"' in html


def test_add_to_cart_redirects_back_and_updates_count(client, food_item):
    response = add(client, food_item, 12)

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/#item-lunch_meeting-{food_item.id}")
    page = client.get("/").get_data(as_text=True)
    assert "Added 12 × Fish soup to your cart" in page and "Cart (1)" in page


def test_add_below_minimum_is_refused(client, food_item):
    response = add(client, food_item, 9)

    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "minimum order is 10 portions" in page
    assert "Cart (0)" in page and "Your cart is empty" in cart_page(client)


@pytest.mark.parametrize("quantity", ["abc", ""])
def test_add_with_non_number_is_refused(client, food_item, quantity):
    add(client, food_item, quantity)

    assert "whole number" in client.get("/").get_data(as_text=True)
    assert "Your cart is empty" in cart_page(client)


def test_adding_hidden_or_unknown_dish_gives_404(client, app, food_item):
    with app.app_context():
        food_item.published = False
        FoodItemRepository().update(food_item)

    assert add(client, food_item, 10).status_code == 404
    assert client.post("/cart/add", data={"food_item_id": 999, "quantity": 10}).status_code == 404


def test_cart_page_shows_lines_and_estimated_total(client, food_item, cake):
    add(client, food_item, 12)
    add(client, cake, 5)

    html = cart_page(client)
    assert "Fish soup" in html and "Coffee and cake" in html
    assert "2268 NOK" in html and "425 NOK" in html  # 12 × 189 and 5 × 85
    assert "Estimated total: <strong>2693 NOK</strong>" in html


def test_update_with_one_bad_line_saves_nothing(client, food_item, cake):
    add(client, food_item, 12)
    add(client, cake, 5)

    response = client.post("/cart/update", data={f"qty-{food_item.id}": "20", f"qty-{cake.id}": "2"})

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Coffee and cake: the minimum order is 5 portions" in html
    assert 'value="2"' in html  # the customer's input is kept so they can fix it
    assert "Estimated total: <strong>2693 NOK</strong>" in cart_page(client)  # unchanged


def test_valid_update_saves_and_zero_removes(client, food_item, cake):
    add(client, food_item, 12)
    add(client, cake, 5)

    client.post("/cart/update", data={f"qty-{food_item.id}": "20", f"qty-{cake.id}": "0"})

    html = cart_page(client)
    assert "<strong>Coffee and cake</strong>" not in html
    assert "Estimated total: <strong>3780 NOK</strong>" in html  # 20 × 189


def test_remove_button(client, food_item, cake):
    add(client, food_item, 12)
    add(client, cake, 5)

    client.post(f"/cart/remove/{cake.id}")

    html = cart_page(client)
    assert "<strong>Coffee and cake</strong>" not in html and "<strong>Fish soup</strong>" in html


def test_dish_unpublished_while_in_cart_is_dropped(client, app, food_item, cake):
    add(client, food_item, 12)
    add(client, cake, 5)
    with app.app_context():
        cake.published = False
        FoodItemRepository().update(cake)

    html = cart_page(client)
    assert "Coffee and cake is no longer on the menu and was removed" in html
    assert "Estimated total: <strong>2268 NOK</strong>" in html
    assert "Cart (1)" in client.get("/").get_data(as_text=True)


def test_cart_survives_login_and_is_emptied_on_logout(client, food_item, customer):
    add(client, food_item, 12)
    assert "Log in to order" in cart_page(client)

    response = login(client, customer.email, next="/cart")
    assert response.headers["Location"].endswith("/cart")
    html = cart_page(client)
    assert "Fish soup" in html and "Continue to order" in html

    client.post("/account/logout")
    assert "Your cart is empty" in cart_page(client)


def test_cart_with_csrf_enabled(tmp_path):
    app = create_app(TestConfig, CSRF_ENABLED=True, DATABASE=str(tmp_path / "csrf.sqlite"))
    with app.app_context():
        init_db()
        item = FoodItemRepository().add(FoodItem(name_en="Fish soup", name_no="Fiskesuppe", price_nok=189,
                                                 categories={EventCategory.CONFERENCE}, min_order_quantity=10))
    client = app.test_client()
    token = lambda html: re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    assert client.post("/cart/add", data={"food_item_id": item.id, "quantity": 10}).status_code == 400

    menu = client.get("/").get_data(as_text=True)
    client.post("/cart/add", data={"food_item_id": item.id, "quantity": 10, "csrf_token": token(menu)})
    html = client.get("/cart").get_data(as_text=True)
    assert "Estimated total: <strong>1890 NOK</strong>" in html

    client.post("/cart/update", data={f"qty-{item.id}": "15", "csrf_token": token(html)})
    assert "Estimated total: <strong>2835 NOK</strong>" in client.get("/cart").get_data(as_text=True)
