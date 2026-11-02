import re
from datetime import date, timedelta
from typing import Optional

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.controllers.auth import image_response, login_required
from app.models import (Cart, CartError, DeliveryMethod, EventCategory, GuestGroup, ImageError, Order)
from app.models.repositories import FoodItemRepository, ImageStore, OrderRepository, SessionCartRepository

bp = Blueprint("shop", __name__)


@bp.route("/")
def index():
    items = FoodItemRepository().list_all(published_only=True)
    menu = {category: [i for i in items if category in i.categories] for category in EventCategory}
    return render_template("shop/index.html", menu=menu)


@bp.route("/images/<filename>")
def image(filename):
    try:
        data = ImageStore().read_food(filename)
    except ImageError:
        abort(404)
    return image_response(data, ImageStore.mime_type(filename))


# ----------------------------------------------------------------- C2 shopping cart

def _parse_quantity(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@bp.route("/cart/add", methods=["POST"])
def add_to_cart():
    item_id = _parse_quantity(request.form.get("food_item_id"))
    item = FoodItemRepository().get(item_id) if item_id is not None else None
    if item is None or not item.published:
        abort(404)
    quantity = _parse_quantity(request.form.get("quantity"))
    repo = SessionCartRepository()
    cart = repo.load()
    try:
        if quantity is None:
            raise CartError("Enter the number of portions as a whole number.")
        cart.add(item, quantity)
    except CartError as e:
        flash(str(e), "error")
    else:
        repo.save(cart)
        flash(f"Added {quantity} × {item.name_en} to your cart.", "success")
    section = request.form.get("section", "")
    anchor = f"item-{section}-{item.id}" if section in EventCategory._value2member_map_ else None
    return redirect(url_for("shop.index", _anchor=anchor))


def _cart_lines():
    """Load the cart with current prices; dishes that left the menu are dropped and saved."""
    repo = SessionCartRepository()
    cart = repo.load()
    lines, removed = cart.lines(FoodItemRepository().get_many(cart.quantities))
    if removed:
        repo.save(cart)
    return cart, lines, removed


@bp.route("/cart")
def cart():
    cart, lines, removed = _cart_lines()
    for name in removed:
        flash(f"{name} is no longer on the menu and was removed from your cart.", "error")
    return render_template("shop/cart.html", lines=lines, total_nok=cart.total_nok(lines),
                           errors=[], entered={})


@bp.route("/cart/update", methods=["POST"])
def update_cart():
    cart, lines, _ = _cart_lines()
    errors, entered = [], {}
    for line in lines:
        item = line.food_item
        raw = request.form.get(f"qty-{item.id}", str(line.quantity))
        entered[item.id] = raw
        quantity = _parse_quantity(raw)
        try:
            if quantity is None or quantity < 0:
                raise CartError(f"{item.name_en}: enter the number of portions as a whole number.")
            cart.set_quantity(item, quantity)
        except CartError as e:
            errors.append(str(e))
    if errors:
        # Nothing is saved when any line is invalid; show the original cart with the customer's input.
        original, lines, _ = _cart_lines()
        return render_template("shop/cart.html", lines=lines, total_nok=original.total_nok(lines),
                               errors=errors, entered=entered), 400
    SessionCartRepository().save(cart)
    flash("Your cart was updated.", "success")
    return redirect(url_for("shop.cart"))


@bp.route("/cart/remove/<int:item_id>", methods=["POST"])
def remove_from_cart(item_id):
    repo = SessionCartRepository()
    cart = repo.load()
    cart.remove(item_id)
    repo.save(cart)
    flash("The dish was removed from your cart.", "success")
    return redirect(url_for("shop.cart"))


# ----------------------------------------------------------------- C3 checkout

GUEST_ROWS_SHOWN = 3


def _guest_groups_from_form(form, errors: list[str]) -> list[GuestGroup]:
    """Read guest-group rows (group_label-N, group_count-N, group_notes-N). Empty rows are ignored."""
    indices = set()
    for key in form:
        match = re.fullmatch(r"group_(?:label|count|notes)-(\d+)", key)
        if match:
            indices.add(int(match.group(1)))
    groups = []
    for i in sorted(indices):
        label = form.get(f"group_label-{i}", "").strip()
        count_text = form.get(f"group_count-{i}", "").strip()
        notes = form.get(f"group_notes-{i}", "").strip()
        if not (label or count_text or notes):
            continue
        count = _parse_quantity(count_text)
        if count is None:
            errors.append(f"{label or f'Guest group {len(groups) + 1}'}: enter the number of guests as a whole number.")
            count = 0
        groups.append(GuestGroup(guest_count=count, label=label or None, diet_notes=notes or None))
    return groups


def _render_checkout(lines, cart, form, errors, status=200):
    sent_rows = [int(k.rsplit("-", 1)[1]) for k in form if re.fullmatch(r"group_\w+-\d+", k)]
    rows = max([GUEST_ROWS_SHOWN] + [i + 1 for i in sent_rows])
    return render_template("shop/checkout.html", lines=lines, total_nok=cart.total_nok(lines), form=form,
                           errors=errors, guest_rows=rows, event_categories=list(EventCategory),
                           delivery_methods=list(DeliveryMethod),
                           min_date=date.today() + timedelta(days=Order.MIN_DAYS_AHEAD)), status


@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart, lines, removed = _cart_lines()
    for name in removed:
        flash(f"{name} is no longer on the menu and was removed from your cart.", "error")
    if not lines:
        flash("Your cart is empty. Add dishes from the menu before ordering.", "error")
        return redirect(url_for("shop.cart"))
    if request.method == "GET":
        return _render_checkout(lines, cart, {}, [])

    form = request.form
    errors = []
    # The menu may have changed since the dishes were added: check the minimum order again.
    for line in lines:
        error = Cart.validate_quantity(line.food_item, line.quantity)
        if error:
            errors.append(error + " Please update your cart.")
    try:
        event_date = date.fromisoformat(form.get("event_date", ""))
    except ValueError:
        errors.append("Choose the date of the event.")
        event_date = date.today()
    event_type = EventCategory._value2member_map_.get(form.get("event_type", ""))
    if event_type is None:
        errors.append("Choose the kind of event.")
    delivery_method = DeliveryMethod._value2member_map_.get(form.get("delivery_method", ""), DeliveryMethod.DELIVERY)
    guest_groups = _guest_groups_from_form(form, errors)

    order = Order.from_cart(
        g.user.id, lines, guest_groups,
        event_type=event_type or EventCategory.OTHER, event_date=event_date, delivery_method=delivery_method,
        delivery_address=form.get("delivery_address", "").strip() or None,
    )
    errors += order.validate(date.today())
    if errors:
        return _render_checkout(lines, cart, form, errors, status=400)

    OrderRepository().add(order)
    SessionCartRepository().clear()
    flash(f"Order {order.order_number} was sent. Ekte Mat will confirm it.", "success")
    return redirect(url_for("account.order_detail", order_id=order.id))
