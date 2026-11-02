import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from werkzeug.security import check_password_hash, generate_password_hash


@dataclass
class Customer:
    """A customer account. Admins are customers with is_admin=True (simplification of StaffUser)."""
    name: str
    email: str
    customer_type: str = "private"  # "private" or "corporate"
    phone: Optional[str] = None
    organisation_number: Optional[str] = None
    password_hash: str = ""
    is_admin: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None

    MIN_PASSWORD_LENGTH = 8

    def validate_registration(self, password: str, confirm: str) -> list[str]:
        errors = []
        if not self.name.strip():
            errors.append("Name is required.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.email):
            errors.append("Enter a valid e-mail address.")
        if self.customer_type not in ("private", "corporate"):
            errors.append("Choose private or corporate customer.")
        if self.customer_type == "corporate" and not re.fullmatch(r"\d{9}", self.organisation_number or ""):
            errors.append("Corporate customers need a 9-digit organisation number.")
        if len(password) < self.MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {self.MIN_PASSWORD_LENGTH} characters.")
        if password != confirm:
            errors.append("The passwords do not match.")
        return errors

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)
