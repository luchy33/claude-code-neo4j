from typing import Optional

from app.models.customer import Customer
from app.models.repositories.db import next_ids, query, to_db_time, to_native, write


class CustomerRepository:
    def add(self, customer: Customer) -> Customer:
        props = {
            "name": customer.name, "email": customer.email, "phone": customer.phone,
            "customer_type": customer.customer_type, "organisation_number": customer.organisation_number,
            "password_hash": customer.password_hash, "is_admin": customer.is_admin,
            "created_at": to_db_time(customer.created_at),
        }

        def create(tx):
            [customer_id] = next_ids(tx, "Customer")
            tx.run("CREATE (c:Customer {id: $id}) SET c += $props", id=customer_id, props=props).consume()
            return customer_id

        customer.id = write(create)
        return customer

    def get(self, customer_id: int) -> Optional[Customer]:
        return self._one("MATCH (c:Customer {id: $value}) RETURN c", customer_id)

    def get_by_email(self, email: str) -> Optional[Customer]:
        return self._one("MATCH (c:Customer {email: $value}) RETURN c", email)

    def get_by_organisation_number(self, organisation_number: str) -> Optional[Customer]:
        return self._one("MATCH (c:Customer {organisation_number: $value}) RETURN c", organisation_number)

    def get_many(self, ids) -> dict[int, Customer]:
        ids = list(set(ids))
        if not ids:
            return {}
        records = query("MATCH (c:Customer) WHERE c.id IN $ids RETURN c", ids=ids)
        return {r["c"]["id"]: self._to_customer(r["c"]) for r in records}

    def list_all(self) -> list[Customer]:
        return [self._to_customer(r["c"]) for r in query("MATCH (c:Customer) RETURN c ORDER BY c.name")]

    def _one(self, cypher: str, value) -> Optional[Customer]:
        records = query(cypher, value=value)
        return self._to_customer(records[0]["c"]) if records else None

    @staticmethod
    def _to_customer(node) -> Customer:
        return Customer(
            id=node["id"],
            name=node["name"],
            email=node["email"],
            phone=node.get("phone"),
            customer_type=node["customer_type"],
            organisation_number=node.get("organisation_number"),
            password_hash=node["password_hash"],
            is_admin=node["is_admin"],
            created_at=to_native(node["created_at"]),
        )
