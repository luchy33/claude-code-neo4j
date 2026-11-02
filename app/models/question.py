from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Question:
    """A customer's question about one of their orders (C5), answered by Ekte Mat in the admin panel (A4)."""
    order_id: int
    name: str
    email: str
    subject: str
    body: str
    customer_id: Optional[int] = None
    answer: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    answered_at: Optional[datetime] = None
    id: Optional[int] = None

    MAX_SUBJECT = 120
    MAX_TEXT = 2000

    @classmethod
    def for_order(cls, order, customer, subject: str, body: str) -> "Question":
        return cls(order_id=order.id, customer_id=customer.id, name=customer.name, email=customer.email,
                   subject=subject.strip(), body=body.strip())

    def validate(self) -> list[str]:
        errors = []
        if not self.subject:
            errors.append("Write a short subject.")
        elif len(self.subject) > self.MAX_SUBJECT:
            errors.append(f"Keep the subject under {self.MAX_SUBJECT} characters.")
        if not self.body:
            errors.append("Write your question.")
        elif len(self.body) > self.MAX_TEXT:
            errors.append(f"Keep the question under {self.MAX_TEXT} characters.")
        return errors

    def give_answer(self, text: str, now: datetime) -> None:
        """Answer the question, or change an earlier answer."""
        text = (text or "").strip()
        if not text:
            raise ValueError("Write an answer before sending.")
        if len(text) > self.MAX_TEXT:
            raise ValueError(f"Keep the answer under {self.MAX_TEXT} characters.")
        self.answer = text
        self.answered_at = now

    @property
    def is_answered(self) -> bool:
        return bool(self.answer)
