from typing import Optional

from app.models.question import Question
from app.models.repositories.db import next_ids, query, to_db_time, to_native, write

# Every question with its order and (if the customer still exists) the customer who asked it.
MATCH_QUESTION = "MATCH (q:Question)-[:ABOUT]->(o:Order)"
QUESTION = "OPTIONAL MATCH (c:Customer)-[:ASKED]->(q) RETURN q {.*, order_id: o.id, customer_id: c.id} AS question"


class QuestionRepository:
    def add(self, question: Question) -> Question:
        def create(tx):
            [question_id] = next_ids(tx, "Question")
            created = tx.run(
                "MATCH (o:Order {id: $order_id}) CREATE (q:Question {id: $id})-[:ABOUT]->(o) SET q += $props RETURN q",
                order_id=question.order_id, id=question_id,
                props={"name": question.name, "email": question.email, "subject": question.subject,
                       "body": question.body, "answer": question.answer,
                       "created_at": to_db_time(question.created_at),
                       "answered_at": to_db_time(question.answered_at)},
            ).single()
            if created is None:
                raise ValueError(f"Unknown order {question.order_id}.")
            if question.customer_id is not None:
                tx.run("MATCH (c:Customer {id: $customer_id}), (q:Question {id: $id}) CREATE (c)-[:ASKED]->(q)",
                       customer_id=question.customer_id, id=question_id).consume()
            return question_id

        question.id = write(create)
        return question

    def get(self, question_id: int) -> Optional[Question]:
        records = query(f"{MATCH_QUESTION} WHERE q.id = $id {QUESTION}", id=question_id)
        return self._to_question(records[0]["question"]) if records else None

    def list_by_order(self, order_id: int) -> list[Question]:
        """Oldest first, so the conversation reads from top to bottom."""
        records = query(f"{MATCH_QUESTION} WHERE o.id = $order_id {QUESTION} ORDER BY q.created_at, q.id",
                        order_id=order_id)
        return [self._to_question(r["question"]) for r in records]

    def search(self, answered: Optional[bool] = None) -> list[Question]:
        """Unanswered questions first, then newest first."""
        where = ""
        if answered is True:
            where = " WHERE q.answer IS NOT NULL"
        elif answered is False:
            where = " WHERE q.answer IS NULL"
        records = query(f"{MATCH_QUESTION}{where} {QUESTION}"
                        " ORDER BY q.answer IS NOT NULL, q.created_at DESC, q.id DESC")
        return [self._to_question(r["question"]) for r in records]

    def list_all(self) -> list[Question]:
        return self.search()

    def save_answer(self, question: Question) -> None:
        query("MATCH (q:Question {id: $id}) SET q.answer = $answer, q.answered_at = $answered_at",
              id=question.id, answer=question.answer, answered_at=to_db_time(question.answered_at))

    def count_unanswered(self) -> int:
        return query("MATCH (q:Question) WHERE q.answer IS NULL RETURN count(q) AS n")[0]["n"]

    def count_by_order(self, order_ids) -> dict[int, tuple[int, int]]:
        """order id -> (number of questions, number still unanswered)."""
        ids = list(set(order_ids))
        if not ids:
            return {}
        records = query(f"{MATCH_QUESTION} WHERE o.id IN $ids"
                        " RETURN o.id AS order_id, count(q) AS total,"
                        " sum(CASE WHEN q.answer IS NULL THEN 1 ELSE 0 END) AS unanswered", ids=ids)
        return {r["order_id"]: (r["total"], r["unanswered"]) for r in records}

    @staticmethod
    def _to_question(data) -> Question:
        return Question(
            id=data["id"],
            order_id=data["order_id"],
            customer_id=data["customer_id"],
            name=data["name"],
            email=data["email"],
            subject=data["subject"],
            body=data["body"],
            answer=data.get("answer"),
            created_at=to_native(data["created_at"]),
            answered_at=to_native(data.get("answered_at")),
        )
