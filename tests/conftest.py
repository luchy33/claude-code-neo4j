import pytest
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

from app import create_app
from app.models import Customer, EventCategory, FoodItem
from app.models.repositories import CustomerRepository, FoodItemRepository
from app.models.repositories.db import close_driver, init_db
from config import Config, TestConfig

PASSWORD = "secret-pass-1"


@pytest.fixture(scope="session")
def neo4j_available():
    """Skip database tests when the neo4j-test container is not running."""
    if TestConfig.NEO4J_URI == Config.NEO4J_URI:
        pytest.exit("TEST_NEO4J_URI points at the dev database. The tests would delete its data.", returncode=1)
    try:
        with GraphDatabase.driver(TestConfig.NEO4J_URI,
                                  auth=(TestConfig.NEO4J_USER, TestConfig.NEO4J_PASSWORD)) as driver:
            driver.verify_connectivity()
    except (ServiceUnavailable, AuthError, OSError) as error:
        pytest.skip(f"Neo4j test database not reachable ({error}) – run: docker compose up -d neo4j-test")


@pytest.fixture
def make_app(neo4j_available, tmp_path):
    """make_app(**overrides): an app on an empty test database. Every call starts from scratch."""
    apps = []

    def make(**overrides):
        app = create_app(TestConfig, UPLOAD_FOLDER=str(tmp_path / "uploads"), **overrides)
        with app.app_context():
            init_db()
        apps.append(app)
        return app
    yield make
    for app in apps:
        close_driver(app)


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()


def _add_customer(app, **fields) -> Customer:
    with app.app_context():
        customer = Customer(**fields)
        customer.set_password(PASSWORD)
        return CustomerRepository().add(customer)


@pytest.fixture
def customer(app):
    return _add_customer(app, name="Test Customer", email="customer@example.com")


@pytest.fixture
def admin(app):
    return _add_customer(app, name="Test Admin", email="admin@example.com", is_admin=True)


def login(client, email, password=PASSWORD, **extra):
    return client.post("/account/login", data={"email": email, "password": password, **extra})


@pytest.fixture
def admin_client(client, admin):
    login(client, admin.email)
    return client


@pytest.fixture
def food_item(app):
    with app.app_context():
        return FoodItemRepository().add(FoodItem(
            name_en="Fish soup", name_no="Fiskesuppe", price_nok=189,
            categories={EventCategory.LUNCH_MEETING}, min_order_quantity=10))


@pytest.fixture
def make_order(app, food_item):
    """Create an order directly in the database: make_order(customer, event_date=..., status=...)."""
    from datetime import date, timedelta

    from app.models import DeliveryMethod, GuestGroup, Order, OrderLine
    from app.models.repositories import OrderRepository

    def make(customer, event_date=None, status=None, payment_status=None, notes=None):
        order = Order(order_number="", customer_id=customer.id, event_type=EventCategory.LUNCH_MEETING,
                      event_date=event_date or date.today() + timedelta(days=10),
                      delivery_method=DeliveryMethod.PICK_UP,
                      guest_groups=[GuestGroup(10, "Main group"), GuestGroup(2, "Allergies", notes)],
                      lines=[OrderLine(food_item.id, 12, food_item.price_nok)])
        if status:
            order.status = status
        if payment_status:
            order.payment_status = payment_status
        with app.app_context():
            return OrderRepository().add(order)
    return make
