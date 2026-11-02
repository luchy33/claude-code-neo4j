from datetime import date

import pytest

from app.models import (Allergen, DeliveryMethod, DietaryLabel, EventCategory, FoodItem,
                        FoodItemInUseError, GuestGroup, Order, OrderLine)
from app.models.repositories import CustomerRepository, FoodItemRepository, OrderRepository

FORM = {
    "name_en": "Lamb stew", "name_no": "Lammegryte", "description": "Slow-cooked.",
    "price_nok": "245", "min_order_quantity": "12",
    "categories": ["wedding", "conference"], "allergens": ["milk", "celery"],
    "dietary_labels": ["gluten_free"], "published": "on",
}


def test_repository_round_trip_keeps_value_sets(app):
    with app.app_context():
        repo = FoodItemRepository()
        item = repo.add(FoodItem(
            name_en="Salad", name_no="Salat", price_nok=165, min_order_quantity=8,
            categories={EventCategory.BIRTHDAY, EventCategory.WEDDING},
            allergens={Allergen.MILK, Allergen.MUSTARD},
            dietary_labels={DietaryLabel.VEGETARIAN}))
        loaded = repo.get(item.id)

        assert loaded.categories == {EventCategory.BIRTHDAY, EventCategory.WEDDING}
        assert loaded.allergens == {Allergen.MILK, Allergen.MUSTARD}
        assert loaded.dietary_labels == {DietaryLabel.VEGETARIAN}
        assert (loaded.price_nok, loaded.min_order_quantity, loaded.published) == (165, 8, True)

        loaded.categories = {EventCategory.CONFERENCE}
        loaded.allergens = set()
        repo.update(loaded)
        reloaded = repo.get(item.id)
        assert reloaded.categories == {EventCategory.CONFERENCE}
        assert reloaded.allergens == set()
        assert [i.id for i in repo.list_by_category(EventCategory.CONFERENCE)] == [item.id]


@pytest.mark.parametrize("changes, message", [
    ({"name_en": " "}, "English name"),
    ({"name_no": ""}, "Norwegian name"),
    ({"price_nok": -1}, "negative"),
    ({"min_order_quantity": 0}, "at least 1"),
    ({"categories": set()}, "event category"),
])
def test_validate_reports_each_error(changes, message):
    fields = dict(name_en="Soup", name_no="Suppe", price_nok=100, categories={EventCategory.OTHER})
    item = FoodItem(**{**fields, **changes})

    errors = item.validate()
    assert len(errors) == 1 and message in errors[0]


def test_admin_creates_food_item(admin_client, app):
    response = admin_client.post("/admin/food-items/new", data=FORM)

    assert response.status_code == 302 and "/image" in response.headers["Location"]
    with app.app_context():
        [item] = FoodItemRepository().list_all()
    assert item.name_en == "Lamb stew" and item.price_nok == 245 and item.min_order_quantity == 12
    assert item.categories == {EventCategory.WEDDING, EventCategory.CONFERENCE}
    assert item.allergens == {Allergen.MILK, Allergen.CELERY}
    assert item.dietary_labels == {DietaryLabel.GLUTEN_FREE}

    shop = admin_client.get("/").get_data(as_text=True)
    assert "Lamb stew" in shop and "Wedding" in shop and "Celery" in shop and "Gluten free" in shop


def test_admin_form_shows_errors(admin_client, app):
    response = admin_client.post("/admin/food-items/new",
                                 data={**FORM, "price_nok": "abc", "categories": []})

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Price must be a whole number" in html and "Choose at least one event category" in html
    with app.app_context():
        assert FoodItemRepository().list_all() == []


def test_admin_edits_and_unpublishes(admin_client, app, food_item):
    unpublished = {k: v for k, v in FORM.items() if k != "published"}  # unticked checkbox is not sent
    response = admin_client.post(f"/admin/food-items/{food_item.id}/edit",
                                 data={**unpublished, "name_en": "Better fish soup"})

    assert response.status_code == 302
    with app.app_context():
        item = FoodItemRepository().get(food_item.id)
    assert item.name_en == "Better fish soup" and not item.published
    assert "<h4>Better fish soup</h4>" not in admin_client.get("/").get_data(as_text=True)
    assert "Better fish soup" in admin_client.get("/admin/food-items").get_data(as_text=True)


def test_admin_deletes_food_item(admin_client, app, food_item):
    admin_client.post(f"/admin/food-items/{food_item.id}/delete")

    with app.app_context():
        assert FoodItemRepository().get(food_item.id) is None


def test_food_item_in_an_order_cannot_be_deleted(admin_client, app, food_item, customer):
    with app.app_context():
        OrderRepository().add(Order(
            order_number="T-1", customer_id=customer.id, event_type=EventCategory.LUNCH_MEETING,
            event_date=date(2027, 3, 1), delivery_method=DeliveryMethod.PICK_UP,
            guest_groups=[GuestGroup(10)], lines=[OrderLine(food_item.id, 10, 189)]))
        with pytest.raises(FoodItemInUseError):
            FoodItemRepository().delete(food_item.id)

    response = admin_client.post(f"/admin/food-items/{food_item.id}/delete", follow_redirects=True)
    assert "Unpublish it instead" in response.get_data(as_text=True)
    with app.app_context():
        assert FoodItemRepository().get(food_item.id) is not None


def test_customer_cannot_change_food_items(client, customer, food_item):
    from tests.conftest import login
    login(client, customer.email)

    assert client.post("/admin/food-items/new", data=FORM).status_code == 403
    assert client.post(f"/admin/food-items/{food_item.id}/delete").status_code == 403
