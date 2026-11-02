import re
from datetime import date, datetime, timedelta

from app import create_app
from app.models import EventCategory, FoodItem, Question
from app.models.repositories import FoodItemRepository, QuestionRepository
from app.models.repositories.db import init_db
from config import TestConfig
from tests.conftest import PASSWORD, _add_customer, login


def add_question(app, order, customer, subject="Delivery time", body="Can you deliver at 17:00?", answer=None,
                 created_at=None):
    with app.app_context():
        question = Question.for_order(order, customer, subject, body)
        if created_at:
            question.created_at = created_at
        if answer:
            question.give_answer(answer, datetime.now())
        return QuestionRepository().add(question)


# ----------------------------------------------------------------- C5 customer asks and reads answers

def test_customer_asks_question_on_own_order(client, app, customer, make_order):
    order = make_order(customer)
    login(client, customer.email)

    response = client.post(f"/account/orders/{order.id}/questions",
                           data={"subject": "Delivery time", "body": "Can you deliver at 17:00?"})

    assert response.status_code == 302 and response.headers["Location"].endswith(f"/account/orders/{order.id}#questions")
    html = client.get(f"/account/orders/{order.id}").get_data(as_text=True)
    assert "Can you deliver at 17:00?" in html and "Waiting for an answer" in html
    with app.app_context():
        [saved] = QuestionRepository().list_by_order(order.id)
    assert saved.customer_id == customer.id and saved.email == customer.email


def test_invalid_question_keeps_input(client, app, customer, make_order):
    order = make_order(customer)
    login(client, customer.email)

    response = client.post(f"/account/orders/{order.id}/questions", data={"subject": "", "body": "My draft text"})

    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Write a short subject." in html and "My draft text" in html
    with app.app_context():
        assert QuestionRepository().list_by_order(order.id) == []


def test_cannot_ask_on_other_customers_order(client, app, customer, make_order):
    other = _add_customer(app, name="Other", email="other@example.com")
    theirs = make_order(other)
    login(client, customer.email)

    data = {"subject": "Hi", "body": "Hello"}
    assert client.post(f"/account/orders/{theirs.id}/questions", data=data).status_code == 404
    assert client.post("/account/orders/9999/questions", data=data).status_code == 404
    with app.app_context():
        assert QuestionRepository().list_all() == []


def test_customer_does_not_see_other_customers_questions(client, app, customer, make_order):
    other = _add_customer(app, name="Other", email="other@example.com")
    mine, theirs = make_order(customer), make_order(other)
    add_question(app, theirs, other, subject="Secret question")
    login(client, customer.email)

    assert "Secret question" not in client.get(f"/account/orders/{mine.id}").get_data(as_text=True)


def test_asking_needs_login(client, customer, make_order):
    order = make_order(customer)
    response = client.post(f"/account/orders/{order.id}/questions", data={"subject": "Hi", "body": "Hello"})
    assert response.status_code == 302 and "/account/login" in response.headers["Location"]


def test_my_orders_shows_question_count(client, app, customer, make_order):
    waiting, answered, none = make_order(customer), make_order(customer), make_order(customer)
    add_question(app, waiting, customer)
    add_question(app, waiting, customer, subject="Second")
    add_question(app, answered, customer, answer="Yes.")
    login(client, customer.email)

    html = client.get("/account/orders").get_data(as_text=True)

    assert f'/account/orders/{waiting.id}#questions">2</a>' in html
    assert f'/account/orders/{answered.id}#questions">1</a>' in html
    assert "Waiting" in html and "Answered" in html


def test_ask_form_is_easy_to_find(client, customer, make_order):
    order = make_order(customer)
    login(client, customer.email)

    nav_and_list = client.get("/account/orders").get_data(as_text=True)
    detail = client.get(f"/account/orders/{order.id}").get_data(as_text=True)

    assert 'href="/account/orders"' in client.get("/").get_data(as_text=True)  # "My orders" in the menu
    assert f'/account/orders/{order.id}#ask">Ask a question</a>' in nav_and_list
    assert 'href="#ask"' in detail and 'id="ask"' in detail and "Send question" in detail


# ----------------------------------------------------------------- A4 admin answers

def test_question_pages_are_admin_only(client, app, customer, make_order):
    question = add_question(app, make_order(customer), customer)
    login(client, customer.email)

    assert client.get("/admin/questions").status_code == 403
    assert client.get(f"/admin/questions/{question.id}").status_code == 403
    assert client.post(f"/admin/questions/{question.id}/answer", data={"answer": "Hi"}).status_code == 403


def test_list_shows_waiting_by_default_and_all_on_request(admin_client, app, customer, make_order):
    order = make_order(customer)
    add_question(app, order, customer, subject="Still waiting")
    add_question(app, order, customer, subject="Already answered", answer="Done.")

    waiting = admin_client.get("/admin/questions").get_data(as_text=True)
    everything = admin_client.get("/admin/questions?show=all").get_data(as_text=True)

    assert "Still waiting" in waiting and "Already answered" not in waiting
    assert "Still waiting" in everything and "Already answered" in everything
    assert order.order_number in waiting


def test_detail_shows_question_order_and_earlier_questions(admin_client, app, customer, make_order):
    order = make_order(customer)
    add_question(app, order, customer, subject="First question", created_at=datetime(2026, 1, 1, 10, 0))
    question = add_question(app, order, customer, subject="Second question", body="Can we change the date?")

    html = admin_client.get(f"/admin/questions/{question.id}").get_data(as_text=True)

    assert "Can we change the date?" in html and customer.email in html
    assert f"/admin/orders/{order.id}" in html and order.order_number in html
    assert "First question" in html and "Send answer" in html
    assert admin_client.get("/admin/questions/9999").status_code == 404


def test_admin_answers_and_customer_sees_answer(client, app, admin, customer, make_order):
    order = make_order(customer)
    question = add_question(app, order, customer)
    login(client, admin.email)

    response = client.post(f"/admin/questions/{question.id}/answer", data={"answer": "Yes, 17:00 is fine."})

    assert response.status_code == 302 and response.headers["Location"].endswith("/admin/questions")
    assert "Delivery time" not in client.get("/admin/questions").get_data(as_text=True)
    client.post("/account/logout")
    login(client, customer.email)
    html = client.get(f"/account/orders/{order.id}").get_data(as_text=True)
    assert "Answer from Ekte Mat" in html and "Yes, 17:00 is fine." in html
    assert "Waiting for an answer" not in html


def test_empty_answer_is_refused(admin_client, app, customer, make_order):
    question = add_question(app, make_order(customer), customer)

    response = admin_client.post(f"/admin/questions/{question.id}/answer", data={"answer": "   "})

    assert response.status_code == 400 and "Write an answer before sending." in response.get_data(as_text=True)
    with app.app_context():
        assert not QuestionRepository().get(question.id).is_answered


def test_answer_can_be_updated(admin_client, app, customer, make_order):
    question = add_question(app, make_order(customer), customer, answer="Yes.")
    assert "Update answer" in admin_client.get(f"/admin/questions/{question.id}").get_data(as_text=True)

    admin_client.post(f"/admin/questions/{question.id}/answer", data={"answer": "Yes, before 17:30."})

    with app.app_context():
        assert QuestionRepository().get(question.id).answer == "Yes, before 17:30."


def test_dashboard_shows_waiting_questions(admin_client, app, customer, make_order):
    order = make_order(customer)
    add_question(app, order, customer)
    add_question(app, order, customer, answer="Done.")

    assert "1 waiting for an answer" in admin_client.get("/admin/").get_data(as_text=True)


def test_admin_order_page_lists_questions(admin_client, app, customer, make_order):
    order = make_order(customer)
    question = add_question(app, order, customer, subject="Allergy question")

    html = admin_client.get(f"/admin/orders/{order.id}").get_data(as_text=True)

    assert "Allergy question" in html and f"/admin/questions/{question.id}" in html


# ----------------------------------------------------------------- repository

def test_repository_queries(app, customer, make_order):
    first, second = make_order(customer), make_order(customer)
    old = add_question(app, first, customer, subject="Old", created_at=datetime(2026, 1, 1, 10, 0), answer="Done.")
    new = add_question(app, first, customer, subject="New")
    other = add_question(app, second, customer, subject="Other")

    with app.app_context():
        repo = QuestionRepository()
        assert [q.id for q in repo.list_by_order(first.id)] == [old.id, new.id]
        assert {q.id for q in repo.search(answered=False)} == {new.id, other.id}
        assert [q.id for q in repo.search(answered=True)] == [old.id]
        assert repo.search()[-1].id == old.id  # answered questions come last
        assert repo.count_by_order([first.id, second.id, 9999]) == {first.id: (2, 1), second.id: (1, 1)}
        assert repo.count_by_order([]) == {}
        assert repo.count_unanswered() == 2


# ----------------------------------------------------------------- end to end

def test_question_end_to_end_with_csrf(tmp_path):
    """Customer orders and asks → admin answers → customer reads the answer, all with CSRF tokens."""
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
    order_url = shop.post("/checkout", data={
        "csrf_token": token(form), "event_type": "conference", "delivery_method": "pick_up",
        "event_date": (date.today() + timedelta(days=5)).isoformat(), "group_count-0": "10"}).headers["Location"]
    page = shop.get(order_url).get_data(as_text=True)
    shop.post(f"{order_url}/questions", data={"csrf_token": token(page), "subject": "Parking",
                                              "body": "Is there parking for pick-up?"})

    office.post("/account/login", data={"email": "boss@example.com", "password": PASSWORD,
                                        "csrf_token": token(office.get("/account/login").get_data(as_text=True))})
    with app.app_context():
        [question] = QuestionRepository().search(answered=False)
    page = office.get(f"/admin/questions/{question.id}").get_data(as_text=True)
    office.post(f"/admin/questions/{question.id}/answer",
                data={"csrf_token": token(page), "answer": "Yes, right outside the door."})

    assert "Yes, right outside the door." in shop.get(order_url).get_data(as_text=True)
