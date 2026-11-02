from datetime import datetime
from typing import Optional

from app.models.customer import Customer
from app.models.repositories.db import get_db


class CustomerRepository:
    def add(self, customer: Customer) -> Customer:
        db = get_db()
        cur = db.execute(
            "INSERT INTO customer (name, email, phone, customer_type, organisation_number,"
            " password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (customer.name, customer.email, customer.phone, customer.customer_type,
             customer.organisation_number, customer.password_hash, int(customer.is_admin),
             customer.created_at.isoformat(timespec="seconds")),
        )
        db.commit()
        customer.id = cur.lastrowid
        return customer

    def get(self, customer_id: int) -> Optional[Customer]:
        row = get_db().execute("SELECT * FROM customer WHERE id = ?", (customer_id,)).fetchone()
        return self._to_customer(row) if row else None

    def get_by_email(self, email: str) -> Optional[Customer]:
        row = get_db().execute("SELECT * FROM customer WHERE email = ?", (email,)).fetchone()
        return self._to_customer(row) if row else None

    def get_by_organisation_number(self, organisation_number: str) -> Optional[Customer]:
        row = get_db().execute("SELECT * FROM customer WHERE organisation_number = ?",
                               (organisation_number,)).fetchone()
        return self._to_customer(row) if row else None

    def get_many(self, ids) -> dict[int, Customer]:
        ids = list(set(ids))
        if not ids:
            return {}
        placeholders = ", ".join("?" * len(ids))
        rows = get_db().execute(f"SELECT * FROM customer WHERE id IN ({placeholders})", ids).fetchall()
        return {row["id"]: self._to_customer(row) for row in rows}

    def list_all(self) -> list[Customer]:
        rows = get_db().execute("SELECT * FROM customer ORDER BY name").fetchall()
        return [self._to_customer(r) for r in rows]

    @staticmethod
    def _to_customer(row) -> Customer:
        return Customer(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            phone=row["phone"],
            customer_type=row["customer_type"],
            organisation_number=row["organisation_number"],
            password_hash=row["password_hash"],
            is_admin=bool(row["is_admin"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
