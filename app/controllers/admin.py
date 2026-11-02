from datetime import date, datetime

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request,
                   session, url_for)

from app.controllers.auth import admin_required, image_response
from app.models import (Allergen, DietaryLabel, EventCategory, FoodItem, FoodItemInUseError, ImageError,
                        OrderStatus, PaymentStatus)
from app.models.repositories import (CustomerRepository, FoodItemRepository, ImageStore, OrderRepository,
                                     QuestionRepository)
from app.models.repositories.image_store import extension_of

bp = Blueprint("admin", __name__, url_prefix="/admin")

MAX_INSTRUCTION_LENGTH = 1000


@bp.route("/")
@admin_required
def index():
    return render_template("admin/index.html",
                           submitted_count=OrderRepository().count_by_status(OrderStatus.SUBMITTED),
                           unanswered_count=QuestionRepository().count_unanswered())


# ----------------------------------------------------------------- A1 food items

@bp.route("/food-items")
@admin_required
def food_items():
    return render_template("admin/food_items/list.html", items=FoodItemRepository().list_all())


def _parse_int(value: str, field: str, errors: list[str]) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"{field} must be a whole number.")
        return 0


def _item_from_form(form, item_id=None, image_filename=None) -> tuple[FoodItem, list[str]]:
    errors = []
    item = FoodItem(
        id=item_id,
        name_en=form.get("name_en", "").strip(),
        name_no=form.get("name_no", "").strip(),
        description=form.get("description", "").strip(),
        price_nok=_parse_int(form.get("price_nok"), "Price", errors),
        min_order_quantity=_parse_int(form.get("min_order_quantity"), "Minimum order quantity", errors),
        categories={EventCategory(v) for v in form.getlist("categories") if v in EventCategory._value2member_map_},
        allergens={Allergen(v) for v in form.getlist("allergens") if v in Allergen._value2member_map_},
        dietary_labels={DietaryLabel(v) for v in form.getlist("dietary_labels")
                        if v in DietaryLabel._value2member_map_},
        published="published" in form,
        image_filename=image_filename,
    )
    return item, errors + item.validate()


def _render_form(item, errors):
    return render_template("admin/food_items/form.html", item=item, errors=errors,
                           categories=list(EventCategory), allergens=list(Allergen),
                           dietary_labels=list(DietaryLabel))


@bp.route("/food-items/new", methods=["GET", "POST"])
@admin_required
def new_food_item():
    if request.method == "POST":
        item, errors = _item_from_form(request.form)
        if not errors:
            FoodItemRepository().add(item)
            flash(f"“{item.name_en}” was added. You can now add a picture.", "success")
            return redirect(url_for("admin.food_item_image", item_id=item.id))
        return _render_form(item, errors)
    return _render_form(FoodItem(name_en="", name_no="", price_nok=0), [])


@bp.route("/food-items/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_food_item(item_id):
    repo = FoodItemRepository()
    existing = repo.get(item_id) or abort(404)
    if request.method == "POST":
        item, errors = _item_from_form(request.form, item_id, existing.image_filename)
        if not errors:
            repo.update(item)
            flash(f"“{item.name_en}” was saved.", "success")
            return redirect(url_for("admin.food_items"))
        return _render_form(item, errors)
    return _render_form(existing, [])


@bp.route("/food-items/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_food_item(item_id):
    repo = FoodItemRepository()
    item = repo.get(item_id) or abort(404)
    try:
        repo.delete(item_id)
    except FoodItemInUseError:
        flash(f"“{item.name_en}” is part of existing orders and cannot be deleted. "
              "Unpublish it instead to hide it from the shop.", "error")
    else:
        ImageStore().delete(item.image_filename)
        flash(f"“{item.name_en}” was deleted.", "success")
    return redirect(url_for("admin.food_items"))


# ----------------------------------------------------------------- A2 images

def _pending_for(item_id):
    pending = session.get("pending_image")
    if pending and pending.get("item_id") == item_id:
        return pending["token"]
    return None


def _set_pending(item_id, token):
    old = session.get("pending_image")
    if old:
        ImageStore().discard(old["token"])
    session["pending_image"] = {"item_id": item_id, "token": token}


def _clear_pending():
    session.pop("pending_image", None)


@bp.route("/food-items/<int:item_id>/image")
@admin_required
def food_item_image(item_id):
    item = FoodItemRepository().get(item_id) or abort(404)
    return render_template("admin/food_items/image.html", item=item)


@bp.route("/food-items/<int:item_id>/image/upload", methods=["POST"])
@admin_required
def upload_food_item_image(item_id):
    FoodItemRepository().get(item_id) or abort(404)
    file = request.files.get("image")
    try:
        if file is None or not file.filename:
            raise ImageError("Choose a picture to upload.")
        data = file.read()
        ext = ImageStore.validate_upload(file.filename, data)
        _set_pending(item_id, ImageStore().save_pending(data, ext))
    except ImageError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.food_item_image", item_id=item_id))
    return redirect(url_for("admin.preview_food_item_image", item_id=item_id))


@bp.route("/food-items/<int:item_id>/image/generate", methods=["POST"])
@admin_required
def generate_food_item_image(item_id):
    item = FoodItemRepository().get(item_id) or abort(404)
    instruction = request.form.get("instruction", "").strip()
    base = request.form.get("base", "none")  # "none", "current" (saved image) or "pending" (preview)
    store = ImageStore()
    error_target = "admin.preview_food_item_image" if base == "pending" else "admin.food_item_image"
    try:
        if not instruction:
            raise ImageError("Write an instruction for the picture.")
        if len(instruction) > MAX_INSTRUCTION_LENGTH:
            raise ImageError(f"Keep the instruction under {MAX_INSTRUCTION_LENGTH} characters.")
        current, current_type = None, None
        if base == "pending" and _pending_for(item_id):
            token = _pending_for(item_id)
            current, current_type = store.read_pending(token), extension_of(token)
        elif base == "current" and item.image_filename:
            current, current_type = store.read_food(item.image_filename), extension_of(item.image_filename)
        svg = current_app.extensions["image_generator"].generate(instruction, current, current_type)
        _set_pending(item_id, store.save_pending(svg, "svg"))
    except ImageError as e:
        flash(str(e), "error")
        return redirect(url_for(error_target, item_id=item_id))
    session["last_instruction"] = instruction
    return redirect(url_for("admin.preview_food_item_image", item_id=item_id))


@bp.route("/food-items/<int:item_id>/image/preview")
@admin_required
def preview_food_item_image(item_id):
    item = FoodItemRepository().get(item_id) or abort(404)
    token = _pending_for(item_id)
    if token is None:
        flash("There is no new picture to preview.", "error")
        return redirect(url_for("admin.food_item_image", item_id=item_id))
    return render_template("admin/food_items/image_preview.html", item=item, token=token,
                           last_instruction=session.get("last_instruction", ""))


@bp.route("/food-items/<int:item_id>/image/save", methods=["POST"])
@admin_required
def save_food_item_image(item_id):
    repo = FoodItemRepository()
    item = repo.get(item_id) or abort(404)
    token = _pending_for(item_id)
    if token is None:
        flash("There is no new picture to save.", "error")
        return redirect(url_for("admin.food_item_image", item_id=item_id))
    store = ImageStore()
    try:
        filename = store.promote(token, item_id)
    except ImageError as e:
        _clear_pending()
        flash(str(e), "error")
        return redirect(url_for("admin.food_item_image", item_id=item_id))
    repo.set_image(item_id, filename)
    store.delete(item.image_filename)
    _clear_pending()
    flash(f"The picture for “{item.name_en}” was saved.", "success")
    return redirect(url_for("admin.food_items"))


@bp.route("/food-items/<int:item_id>/image/discard", methods=["POST"])
@admin_required
def discard_food_item_image(item_id):
    token = _pending_for(item_id)
    if token:
        ImageStore().discard(token)
        _clear_pending()
    flash("The new picture was discarded.", "success")
    return redirect(url_for("admin.food_item_image", item_id=item_id))


@bp.route("/images/pending/<token>")
@admin_required
def pending_image(token):
    try:
        data = ImageStore().read_pending(token)
    except ImageError:
        abort(404)
    return image_response(data, ImageStore.mime_type(token))


# ----------------------------------------------------------------- A3 orders

def _date_filter(name: str, errors: list[str]):
    value = request.args.get(name, "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"“{value}” is not a valid date and was ignored.")
        return None


@bp.route("/orders")
@admin_required
def orders():
    errors = []
    status = OrderStatus._value2member_map_.get(request.args.get("status", ""))
    if request.args.get("status") and status is None:
        errors.append("Unknown status filter was ignored.")
    date_from, date_to = _date_filter("date_from", errors), _date_filter("date_to", errors)
    found = OrderRepository().search(status=status, date_from=date_from, date_to=date_to)
    customers = CustomerRepository().get_many(o.customer_id for o in found)
    return render_template("admin/orders/list.html", orders=found, customers=customers, errors=errors,
                           statuses=list(OrderStatus), selected_status=status,
                           date_from=date_from, date_to=date_to)


@bp.route("/orders/<int:order_id>")
@admin_required
def order_detail(order_id):
    order = OrderRepository().get(order_id) or abort(404)
    items = FoodItemRepository().get_many(line.food_item_id for line in order.lines)
    return render_template("admin/orders/detail.html", order=order, items=items,
                           customer=CustomerRepository().get(order.customer_id),
                           payment_statuses=list(PaymentStatus),
                           questions=QuestionRepository().list_by_order(order.id))


@bp.route("/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def change_order_status(order_id):
    repo = OrderRepository()
    order = repo.get(order_id) or abort(404)
    new_status = OrderStatus._value2member_map_.get(request.form.get("status", ""))
    try:
        if new_status is None:
            raise ValueError("Unknown order status.")
        order.change_status(new_status)  # the domain model enforces the allowed transitions
    except ValueError as e:
        flash(str(e), "error")
    else:
        repo.update_status(order)
        flash(f"Order {order.order_number} is now {new_status.label.lower()}.", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@bp.route("/orders/<int:order_id>/payment", methods=["POST"])
@admin_required
def change_payment_status(order_id):
    repo = OrderRepository()
    order = repo.get(order_id) or abort(404)
    new_status = PaymentStatus._value2member_map_.get(request.form.get("payment_status", ""))
    if new_status is None:
        flash("Unknown payment status.", "error")
    else:
        order.payment_status = new_status
        repo.update_status(order)
        flash(f"Payment status for {order.order_number} is now {new_status.label.lower()}.", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


# ----------------------------------------------------------------- A4 questions

@bp.route("/questions")
@admin_required
def questions():
    show_all = request.args.get("show") == "all"
    found = QuestionRepository().search(answered=None if show_all else False)
    orders = {o.id: o for o in (OrderRepository().get(i) for i in {q.order_id for q in found}) if o}
    return render_template("admin/questions/list.html", questions=found, orders=orders, show_all=show_all)


def _render_question(question, answer_text=None, errors=None, status=200):
    order = OrderRepository().get(question.order_id)
    earlier = [q for q in QuestionRepository().list_by_order(question.order_id) if q.id != question.id]
    return render_template("admin/questions/detail.html", question=question, order=order, earlier=earlier,
                           answer_text=question.answer if answer_text is None else answer_text,
                           errors=errors or []), status


@bp.route("/questions/<int:question_id>")
@admin_required
def question_detail(question_id):
    return _render_question(QuestionRepository().get(question_id) or abort(404))


@bp.route("/questions/<int:question_id>/answer", methods=["POST"])
@admin_required
def answer_question(question_id):
    repo = QuestionRepository()
    question = repo.get(question_id) or abort(404)
    text = request.form.get("answer", "")
    try:
        question.give_answer(text, datetime.now())
    except ValueError as e:
        return _render_question(question, text, [str(e)], status=400)
    repo.save_answer(question)
    flash(f"Answer sent to {question.name}.", "success")
    return redirect(url_for("admin.questions"))
