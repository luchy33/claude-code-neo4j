from app.models import OrderStatus, PaymentStatus
from app.models.repositories import OrderRepository
from tests.conftest import _add_customer, login


def test_my_orders_lists_only_own_orders(client, app, customer, make_order):
    other = _add_customer(app, name="Other", email="other@example.com")
    mine = make_order(customer, status=OrderStatus.APPROVED, payment_status=PaymentStatus.DEPOSIT_PAID)
    theirs = make_order(other)
    login(client, customer.email)

    html = client.get("/account/orders").get_data(as_text=True)

    assert mine.order_number in html and theirs.order_number not in html
    assert "Approved" in html and "Deposit paid" in html
    assert "My orders (1)" in client.get("/account/").get_data(as_text=True)


def test_order_detail_for_owner_only(client, app, customer, make_order):
    other = _add_customer(app, name="Other", email="other@example.com")
    mine = make_order(customer, notes="Nut allergy")
    theirs = make_order(other)
    login(client, customer.email)

    html = client.get(f"/account/orders/{mine.id}").get_data(as_text=True)
    assert "Nut allergy" in html and "Fish soup" in html and "2268 NOK" in html
    assert client.get(f"/account/orders/{theirs.id}").status_code == 404
    assert client.get("/account/orders/9999").status_code == 404


def test_my_orders_needs_login(client):
    assert client.get("/account/orders").status_code == 302


def test_customer_sees_status_changed_by_admin(client, app, customer, make_order):
    order = make_order(customer)
    with app.app_context():
        order.change_status(OrderStatus.APPROVED)
        order.payment_status = PaymentStatus.INVOICED
        OrderRepository().update_status(order)
    login(client, customer.email)

    html = client.get(f"/account/orders/{order.id}").get_data(as_text=True)
    assert "status-approved" in html and "payment-invoiced" in html
