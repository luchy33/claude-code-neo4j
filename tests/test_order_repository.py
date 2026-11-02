from datetime import date

from app.models import OrderStatus
from app.models.repositories import OrderRepository


def test_order_numbers_count_up(app, customer, make_order):
    year = date.today().year
    first, second = make_order(customer), make_order(customer)

    assert first.order_number == f"EM-{year}-0001"
    assert second.order_number == f"EM-{year}-0002"


def test_search_filters(app, customer, admin, make_order):
    a = make_order(customer, event_date=date(2027, 1, 10))
    b = make_order(customer, event_date=date(2027, 1, 20), status=OrderStatus.APPROVED)
    c = make_order(admin, event_date=date(2027, 2, 1), status=OrderStatus.APPROVED)

    with app.app_context():
        repo = OrderRepository()
        ids = lambda orders: [o.id for o in orders]

        assert ids(repo.search()) == [a.id, b.id, c.id]  # sorted by event date
        assert ids(repo.search(status=OrderStatus.APPROVED)) == [b.id, c.id]
        assert ids(repo.search(date_from=date(2027, 1, 20))) == [b.id, c.id]  # inclusive
        assert ids(repo.search(date_to=date(2027, 1, 20))) == [a.id, b.id]  # inclusive
        assert ids(repo.search(status=OrderStatus.APPROVED, date_to=date(2027, 1, 31))) == [b.id]
        assert ids(repo.search(customer_id=customer.id)) == [a.id, b.id]
        assert ids(repo.list_by_customer(customer.id)) == [b.id, a.id]  # newest event first
        assert repo.count_by_status(OrderStatus.APPROVED) == 2


def test_round_trip_keeps_groups_lines_and_statuses(app, customer, make_order):
    order = make_order(customer, notes="Nut allergy")

    with app.app_context():
        loaded = OrderRepository().get(order.id)
    assert [(g.label, g.guest_count, g.diet_notes) for g in loaded.guest_groups] == [
        ("Main group", 10, None), ("Allergies", 2, "Nut allergy")]
    assert loaded.total_nok == 12 * 189 and loaded.guest_count == 12
