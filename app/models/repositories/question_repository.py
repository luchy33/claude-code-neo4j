from datetime import datetime
from typing import Optional

from app.models.question import Question
from app.models.repositories.db import get_db


class QuestionRepository:
    def add(self, question: Question) -> Question:
        db = get_db()
        cur = db.execute(
            "INSERT INTO question (order_id, customer_id, name, email, subject, body, answer, created_at, answered_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (question.order_id, question.customer_id, question.name, question.email, question.subject,
             question.body, question.answer, question.created_at.isoformat(timespec="seconds"),
             question.answered_at.isoformat(timespec="seconds") if question.answered_at else None),
        )
        db.commit()
        question.id = cur.lastrowid
        return question

    def get(self, question_id: int) -> Optional[Question]:
        row = get_db().execute("SELECT * FROM question WHERE id = ?", (question_id,)).fetchone()
        return self._to_question(row) if row else None

    def list_by_order(self, order_id: int) -> list[Question]:
        """Oldest first, so the conversation reads from top to bottom."""
        rows = get_db().execute("SELECT * FROM question WHERE order_id = ? ORDER BY created_at, id",
                                (order_id,)).fetchall()
        return [self._to_question(r) for r in rows]

    def search(self, answered: Optional[bool] = None) -> list[Question]:
        """Unanswered questions first, then newest first."""
        where = ""
        if answered is True:
            where = " WHERE answer IS NOT NULL"
        elif answered is False:
            where = " WHERE answer IS NULL"
        rows = get_db().execute(
            f"SELECT * FROM question{where} ORDER BY answer IS NOT NULL, created_at DESC, id DESC"
        ).fetchall()
        return [self._to_question(r) for r in rows]

    def list_all(self) -> list[Question]:
        return self.search()

    def save_answer(self, question: Question) -> None:
        db = get_db()
        db.execute("UPDATE question SET answer = ?, answered_at = ? WHERE id = ?",
                   (question.answer, question.answered_at.isoformat(timespec="seconds"), question.id))
        db.commit()

    def count_unanswered(self) -> int:
        return get_db().execute("SELECT COUNT(*) FROM question WHERE answer IS NULL").fetchone()[0]

    def count_by_order(self, order_ids) -> dict[int, tuple[int, int]]:
        """order id -> (number of questions, number still unanswered)."""
        ids = list(set(order_ids))
        if not ids:
            return {}
        placeholders = ", ".join("?" * len(ids))
        rows = get_db().execute(
            f"SELECT order_id, COUNT(*), SUM(answer IS NULL) FROM question WHERE order_id IN ({placeholders})"
            " GROUP BY order_id", ids,
        ).fetchall()
        return {row[0]: (row[1], row[2]) for row in rows}

    @staticmethod
    def _to_question(row) -> Question:
        return Question(
            id=row["id"],
            order_id=row["order_id"],
            customer_id=row["customer_id"],
            name=row["name"],
            email=row["email"],
            subject=row["subject"],
            body=row["body"],
            answer=row["answer"],
            created_at=datetime.fromisoformat(row["created_at"]),
            answered_at=datetime.fromisoformat(row["answered_at"]) if row["answered_at"] else None,
        )
