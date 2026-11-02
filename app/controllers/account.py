from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.controllers.auth import is_safe_next, log_in, log_out, login_required
from app.models import Customer, Question
from app.models.repositories import CustomerRepository, FoodItemRepository, OrderRepository, QuestionRepository

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.route("/")
@login_required
def index():
    orders = OrderRepository().list_by_customer(g.user.id)
    return render_template("account/index.html", latest_order=orders[0] if orders else None,
                           order_count=len(orders))


# ----------------------------------------------------------------- C4 my orders

@bp.route("/orders")
@login_required
def orders():
    found = OrderRepository().list_by_customer(g.user.id)
    question_counts = QuestionRepository().count_by_order(o.id for o in found)
    return render_template("account/orders.html", orders=found, question_counts=question_counts)


def _own_order_or_404(order_id):
    order = OrderRepository().get(order_id)
    if order is None or order.customer_id != g.user.id:
        abort(404)  # also for other customers' orders, so order ids cannot be guessed
    return order


def _render_order(order, question_form=None, errors=None, status=200):
    items = FoodItemRepository().get_many(line.food_item_id for line in order.lines)
    return render_template("account/order_detail.html", order=order, items=items,
                           questions=QuestionRepository().list_by_order(order.id),
                           question_form=question_form or {}, errors=errors or []), status


@bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    return _render_order(_own_order_or_404(order_id))


# ----------------------------------------------------------------- C5 questions about an order

@bp.route("/orders/<int:order_id>/questions", methods=["POST"])
@login_required
def ask_question(order_id):
    order = _own_order_or_404(order_id)
    question = Question.for_order(order, g.user, request.form.get("subject", ""), request.form.get("body", ""))
    errors = question.validate()
    if errors:
        return _render_order(order, request.form, errors, status=400)
    QuestionRepository().add(question)
    flash("Your question was sent. Ekte Mat will answer here.", "success")
    return redirect(url_for("account.order_detail", order_id=order.id, _anchor="questions"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    errors, form = [], request.form
    next_url = request.values.get("next", "")
    if request.method == "POST":
        customer_type = form.get("customer_type", "private")
        customer = Customer(
            name=form.get("name", "").strip(),
            email=form.get("email", "").strip().lower(),
            phone=form.get("phone", "").strip() or None,
            customer_type=customer_type,
            organisation_number=(form.get("organisation_number", "").replace(" ", "") or None)
            if customer_type == "corporate" else None,
        )
        errors = customer.validate_registration(form.get("password", ""), form.get("confirm_password", ""))
        repo = CustomerRepository()
        if not errors and repo.get_by_email(customer.email):
            errors.append("An account with this e-mail address already exists.")
        if not errors and customer.organisation_number and repo.get_by_organisation_number(customer.organisation_number):
            errors.append("This organisation number is already registered.")
        if not errors:
            customer.set_password(form["password"])
            repo.add(customer)
            log_in(customer)
            flash(f"Welcome, {customer.name}! Your account has been created.", "success")
            # A new customer coming from the cart goes straight on to the order (C3).
            return redirect(next_url if is_safe_next(next_url) else url_for("account.index"))
    return render_template("account/register.html", errors=errors, form=form, next_url=next_url)


@bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.values.get("next", "")
    error = None
    if request.method == "POST":
        customer = CustomerRepository().get_by_email(request.form.get("email", "").strip().lower())
        if customer is None or not customer.check_password(request.form.get("password", "")):
            error = "Wrong e-mail address or password."
        else:
            log_in(customer)
            flash(f"Logged in as {customer.name}.", "success")
            if is_safe_next(next_url):
                return redirect(next_url)
            return redirect(url_for("admin.index" if customer.is_admin else "account.index"))
    return render_template("account/login.html", error=error, next_url=next_url,
                           email=request.form.get("email", ""))


@bp.route("/logout", methods=["POST"])
def logout():
    log_out()
    flash("You have been logged out.", "success")
    return redirect(url_for("shop.index"))
