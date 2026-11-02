import re
from datetime import date, timedelta

import pytest

from app import create_app
from app.models import EventCategory, FoodItem, OrderStatus, PaymentStatus
from app.models.repositories import FoodItemRepository, OrderRepository
from app.models.repositories.db import init_db
from config import TestConfig
from tests.conftest import PASSWORD, _add_customer, login


def status_of(app, order):
    with app.app_context():
        return OrderRepository().get(order.id)


def test_order_pages_are_admin_only(client, customer, make_order):
    order = make_order(customer)
    login(client, customer.email)

    assert client.get("/admin/orders").status_code == 403
    assert client.get(f"/admin/orders/{order.id}").status_code == 403
    assert client.post(f"/admin/orders/{order.id}/status", data={"status": "approved"}).status_code == 403


def test_list_and_filters(admin_client, customer, make_order):
    a = make_order(customer, event_date=date(2027, 1, 10))
    b = make_order(customer, event_date=date(2027, 1, 20), status=OrderStatus.APPROVED)
    c = make_order(customer, event_date=date(2027, 2, 1), status=OrderStatus.APPROVED)
    shown = lambda url: [n for n in (a.order_number, b.order_number, c.order_number)
                         if n in admin_client.get(url).get_data(as_text=True)]

    assert shown("/admin/orders") == [a.order_number, b.order_number, c.order_number]
    assert shown("/admin/orders?status=approved") == [b.order_number, c.order_number]
    assert shown("/admin/orders?date_from=2027-01-15&date_to=2027-01-31") == [b.order_number]
    assert shown("/admin/orders?status=approved&date_from=2027-01-25") == [c.order_number]

    html = admin_client.get("/admin/orders?status=approved&date_from=2027-01-15").get_data(as_text=True)
    assert 'value="2027-01-15"' in html and '<option value="approved" selected>' in html  # filters stay filled in
    assert "Test Customer" in html


def test_bad_filter_values_are_ignored(admin_client, customer, make_order):
    order = make_order(customer)

    html = admin_client.get("/admin/orders?status=flying&date_from=31.12.2026").get_data(as_text=True)
    assert order.order_number in html
    assert "Unknown status filter was ignored" in html and "not a valid date" in html


def test_detail_shows_notes_and_allowed_buttons(admin_client, customer, make_order):
    order = make_order(customer, notes="Nut allergy")

    html = admin_client.get(f"/admin/orders/{order.id}").get_data(as_text=True)
    assert 'class="has-notes"' in html and "Nut allergy" in html
    assert customer.email in html
    buttons = re.findall(r'name="status" value="(\w+)"', html)
    assert buttons == ["approved", "rejected", "cancelled"]


def test_full_status_flow(admin_client, app, customer, make_order):
    order = make_order(customer)
    for status in ("approved", "in_preparation", "delivered"):
        response = admin_client.post(f"/admin/orders/{order.id}/status", data={"status": status},
                                     follow_redirects=True)
        assert "is now" in response.get_data(as_text=True)
        assert status_of(app, order).status.value == status

    html = admin_client.get(f"/admin/orders/{order.id}").get_data(as_text=True)
    assert "Final status" in html and 'name="status"' not in html


def test_illegal_status_change_is_refused(admin_client, app, customer, make_order):
    order = make_order(customer)

    response = admin_client.post(f"/admin/orders/{order.id}/status", data={"status": "delivered"},
                                 follow_redirects=True)
    assert "submitted cannot be changed to delivered" in response.get_data(as_text=True)
    assert status_of(app, order).status == OrderStatus.SUBMITTED

    admin_client.post(f"/admin/orders/{order.id}/status", data={"status": "nonsense"})
    assert status_of(app, order).status == OrderStatus.SUBMITTED


@pytest.mark.parametrize("final", [OrderStatus.REJECTED, OrderStatus.CANCELLED])
def test_rejected_and_cancelled_are_final(admin_client, app, customer, make_order, final):
    order = make_order(customer, status=final)

    assert 'name="status"' not in admin_client.get(f"/admin/orders/{order.id}").get_data(as_text=True)
    admin_client.post(f"/admin/orders/{order.id}/status", data={"status": "approved"})
    assert status_of(app, order).status == final


def test_payment_status_is_saved(admin_client, app, customer, make_order):
    order = make_order(customer)

    admin_client.post(f"/admin/orders/{order.id}/payment", data={"payment_status": "deposit_paid"})
    assert status_of(app, order).payment_status == PaymentStatus.DEPOSIT_PAID

    admin_client.post(f"/admin/orders/{order.id}/payment", data={"payment_status": "free"})
    assert status_of(app, order).payment_status == PaymentStatus.DEPOSIT_PAID


def test_dashboard_shows_waiting_orders(admin_client, customer, make_order):
    make_order(customer)
    make_order(customer, status=OrderStatus.APPROVED)

    assert "1 waiting for approval" in admin_client.get("/admin/").get_data(as_text=True)


def test_end_to_end_with_csrf(tmp_path):
    """Cart → log in → checkout → admin approves → customer sees it, all with CSRF tokens."""
    app = create_app(TestConfig, CSRF_ENABLED=True, DATABASE=str(tmp_path / "e2e.sqlite"))
    with app.app_context():
        init_db()
        item = FoodItemRepository().add(FoodItem(name_en="Fish soup", name_no="Fiskesuppe", price_nok=189,
                                                 categories={EventCategory.CONFERENCE}, min_order_quantity=10))
    customer = _add_customer(app, name="Kari", email="kari@example.com")
    _add_customer(app, name="Admin", email="boss@example.com", is_admin=True)
    token = lambda html: re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    shop, office = app.test_client(), app.test_client()

    shop.post("/cart/add", data={"food_item_id": item.id, "quantity": 10,
                                 "csrf_token": token(shop.get("/").get_data(as_text=True))})
    shop.post("/account/login", data={"email": customer.email, "password": PASSWORD,
                                      "csrf_token": token(shop.get("/account/login").get_data(as_text=True))})
    form = shop.get("/checkout").get_data(as_text=True)
    response = shop.post("/checkout", data={
        "csrf_token": token(form), "event_type": "conference", "delivery_method": "pick_up",
        "event_date": (date.today() + timedelta(days=5)).isoformat(), "group_count-0": "10"})
    order_url = response.headers["Location"]
    order_id = int(order_url.rsplit("/", 1)[1])

    office.post("/account/login", data={"email": "boss@example.com", "password": PASSWORD,
                                        "csrf_token": token(office.get("/account/login").get_data(as_text=True))})
    page = office.get(f"/admin/orders/{order_id}").get_data(as_text=True)
    office.post(f"/admin/orders/{order_id}/status", data={"status": "approved", "csrf_token": token(page)})

    assert "status-approved" in shop.get(order_url).get_data(as_text=True)
