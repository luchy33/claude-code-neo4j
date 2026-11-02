from datetime import datetime

import pytest

from app.models import Customer, Question


def make_question(subject="Delivery time", body="Can you deliver at 17:00?"):
    return Question(order_id=1, name="Kari", email="kari@example.com", subject=subject, body=body)


def test_valid_question_has_no_errors():
    assert make_question().validate() == []


@pytest.mark.parametrize("subject, body, expected", [
    ("", "Question", "Write a short subject."),
    ("x" * 121, "Question", "Keep the subject under 120 characters."),
    ("Subject", "", "Write your question."),
    ("Subject", "x" * 2001, "Keep the question under 2000 characters."),
])
def test_validate_catches_each_error(subject, body, expected):
    assert make_question(subject, body).validate() == [expected]


def test_give_answer_sets_answer_and_time():
    question = make_question()
    assert not question.is_answered
    now = datetime(2026, 10, 28, 12, 0)

    question.give_answer("  Yes, that is fine.  ", now)

    assert question.answer == "Yes, that is fine." and question.answered_at == now and question.is_answered


@pytest.mark.parametrize("text", ["", "   ", None, "x" * 2001])
def test_give_answer_refuses_empty_or_too_long(text):
    question = make_question()
    with pytest.raises(ValueError):
        question.give_answer(text, datetime.now())
    assert not question.is_answered


def test_answer_can_be_changed():
    question = make_question()
    question.give_answer("Yes.", datetime(2026, 10, 28, 12, 0))
    later = datetime(2026, 10, 29, 9, 0)

    question.give_answer("Yes, but only before 17:30.", later)

    assert question.answer == "Yes, but only before 17:30." and question.answered_at == later


def test_for_order_copies_customer_details():
    class FakeOrder:
        id = 7
    customer = Customer("Kari", "kari@example.com")
    customer.id = 3

    question = Question.for_order(FakeOrder(), customer, " Subject ", " Body ")

    assert (question.order_id, question.customer_id, question.name, question.email) == (7, 3, "Kari", "kari@example.com")
    assert (question.subject, question.body) == ("Subject", "Body")
