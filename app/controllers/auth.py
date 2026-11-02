"""Login state, access decorators and CSRF protection shared by all blueprints."""
import secrets
from functools import wraps
from typing import Optional

from flask import abort, current_app, g, make_response, redirect, request, session, url_for

from app.models.repositories import CustomerRepository, SessionCartRepository


def init_app(app) -> None:
    app.before_request(load_logged_in_user)
    app.before_request(check_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.context_processor(lambda: {"cart_count": SessionCartRepository().load().item_count})


def load_logged_in_user() -> None:
    customer_id = session.get("customer_id")
    g.user = CustomerRepository().get(customer_id) if customer_id else None


def log_in(customer) -> None:
    carts = SessionCartRepository()
    cart = carts.load()  # keep the cart: customers fill it before logging in to order (C3)
    session.clear()  # new session on login, so an old session id cannot be reused
    session["customer_id"] = customer.id
    carts.save(cart)


def log_out() -> None:
    session.clear()  # also empties the cart, so the next person on a shared computer starts clean


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("account.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("account.login", next=request.full_path.rstrip("?")))
        if not g.user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def is_safe_next(target: Optional[str]) -> bool:
    """Only allow redirects to local paths such as /admin/ – never to other sites."""
    return bool(target) and target.startswith("/") and not target.startswith("//") and "\\" not in target


def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def check_csrf() -> None:
    if request.method != "POST" or not current_app.config.get("CSRF_ENABLED", True):
        return
    sent = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(sent, expected):
        abort(400, description="The form has expired. Go back, reload the page and try again.")


def image_response(data: bytes, mime_type: str):
    """Serve an image so that even a malicious SVG cannot run scripts on this site."""
    response = make_response(data)
    response.headers["Content-Type"] = mime_type
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
