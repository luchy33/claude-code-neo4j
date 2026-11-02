import re

import pytest

from app import create_app
from app.models.repositories import CustomerRepository
from app.models.repositories.db import init_db
from config import TestConfig
from tests.conftest import PASSWORD, login

REGISTRATION = {
    "name": "New Customer", "email": "New@Example.com", "phone": "", "customer_type": "private",
    "organisation_number": "", "password": "long-enough", "confirm_password": "long-enough",
}


def test_register_creates_account_and_logs_in(client, app):
    response = client.post("/account/register", data=REGISTRATION)

    assert response.status_code == 302 and response.headers["Location"].endswith("/account/")
    with app.app_context():
        saved = CustomerRepository().get_by_email("new@example.com")
    assert saved is not None and not saved.is_admin
    assert saved.check_password("long-enough")
    assert "New Customer" in client.get("/account/").get_data(as_text=True)



def test_register_from_cart_goes_on_to_checkout(client, food_item):
    client.post("/cart/add", data={"food_item_id": food_item.id, "quantity": 10})
    assert "next=/checkout" in client.get("/cart").get_data(as_text=True)

    response = client.post("/account/register", data={**REGISTRATION, "next": "/checkout"})

    assert response.headers["Location"] == "/checkout"
    assert "Fish soup" in client.get("/checkout").get_data(as_text=True)  # the cart was kept


def test_register_ignores_unsafe_next(client):
    response = client.post("/account/register", data={**REGISTRATION, "next": "https://evil.example"})
    assert response.headers["Location"].endswith("/account/")

@pytest.mark.parametrize("changes, message", [
    ({"password": "short", "confirm_password": "short"}, "at least 8 characters"),
    ({"confirm_password": "something-else"}, "do not match"),
    ({"email": "not-an-email"}, "valid e-mail"),
    ({"customer_type": "corporate", "organisation_number": "123"}, "9-digit organisation number"),
])
def test_register_rejects_invalid_input(client, changes, message):
    response = client.post("/account/register", data={**REGISTRATION, **changes})

    assert response.status_code == 200
    assert message in response.get_data(as_text=True)


def test_register_rejects_duplicate_email(client, customer):
    response = client.post("/account/register", data={**REGISTRATION, "email": customer.email})

    assert "already exists" in response.get_data(as_text=True)


def test_corporate_registration_stores_organisation_number(client, app):
    client.post("/account/register", data={**REGISTRATION, "customer_type": "corporate",
                                           "organisation_number": "999 888 777"})

    with app.app_context():
        saved = CustomerRepository().get_by_email("new@example.com")
    assert saved.customer_type == "corporate" and saved.organisation_number == "999888777"


def test_login_with_wrong_password_fails(client, customer):
    response = login(client, customer.email, "wrong-password")

    assert response.status_code == 200
    assert "Wrong e-mail address or password" in response.get_data(as_text=True)
    assert client.get("/account/").status_code == 302


def test_customer_login_and_logout(client, customer):
    response = login(client, customer.email)
    assert response.headers["Location"].endswith("/account/")
    assert client.get("/account/").status_code == 200

    client.post("/account/logout")
    assert client.get("/account/").status_code == 302


def test_admin_lands_in_admin_panel(client, admin):
    response = login(client, admin.email)

    assert response.headers["Location"].endswith("/admin/")


def test_admin_panel_access(client, customer, admin):
    anonymous = client.get("/admin/")
    assert anonymous.status_code == 302 and "/account/login" in anonymous.headers["Location"]

    login(client, customer.email)
    assert client.get("/admin/").status_code == 403
    assert client.get("/admin/food-items").status_code == 403

    client.post("/account/logout")
    login(client, admin.email)
    assert client.get("/admin/").status_code == 200


def test_login_follows_local_next_only(client, customer):
    local = login(client, customer.email, next="/account/")
    assert local.headers["Location"].endswith("/account/")

    client.post("/account/logout")
    outside = login(client, customer.email, next="https://evil.example.com/")
    assert "evil.example.com" not in outside.headers["Location"]


def test_post_without_csrf_token_is_rejected(tmp_path):
    app = create_app(TestConfig, CSRF_ENABLED=True, DATABASE=str(tmp_path / "csrf.sqlite"))
    with app.app_context():
        init_db()
    client = app.test_client()

    assert client.post("/account/login", data={"email": "a@b.no", "password": "x"}).status_code == 400

    page = client.get("/account/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    with_token = client.post("/account/login", data={"email": "a@b.no", "password": "x", "csrf_token": token})
    assert with_token.status_code == 200  # reaches the login check (wrong password), not blocked
