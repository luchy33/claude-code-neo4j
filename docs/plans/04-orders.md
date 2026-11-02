# Plan 04 – Orders: checkout (C3), my orders (C4) and admin order management (A3)

Status: agreed 2026-10-27.

## Context
The Oblig 4 requirements:
- **C3 Order:** log in (or register) and submit the order with the event date, number of guests, delivery address, and allergy and dietary notes per guest group. No payment solution is needed.
- **C4 My orders:** the customer's own orders, with their current status and payment status.
- **A3 Orders:** a list of all orders that can be filtered by status and event date, and a page per order to manage the order status (submitted → approved → in preparation → delivered, or rejected/cancelled) and the payment status.

The three share one domain object, `Order`, so they are planned together.

**What already exists:**
- [app/models/order.py](app/models/order.py) has `Order`, `GuestGroup` and `OrderLine`, which stores `unit_price_nok` as copied at order time. `Order.ALLOWED_TRANSITIONS` and `change_status()` already match A3's state machine exactly. There are `total_nok` and `guest_count` properties.
- [app/models/repositories/order_repository.py](app/models/repositories/order_repository.py) has `add`, which saves the order, its groups and its lines in one transaction, plus `get`, `list_all`, `list_by_customer` and `update_status`.
- C2's `Cart` keeps itself across login, and its "Continue to order" button is waiting for C3.
- **No database change is needed**, so teammates don't have to rebuild their database. They only need to run the seed if they want the new demo orders.

Everything still follows CLAUDE.md: the rules are in the domain, only repositories touch storage, there are CSRF tokens and `@admin_required`, the text is in British English, prices are in NOK, and every feature has tests.

## 1 Domain model ([app/models/order.py](app/models/order.py))
- `Order.MIN_DAYS_AHEAD = 1`: the event must be at least tomorrow. This is a simple rule the kitchen can change later.
- `Order.validate(today) -> list[str]` checks:
  - the cart has at least one line;
  - the event date is at least `today + MIN_DAYS_AHEAD`;
  - there is at least one guest group, and each has `guest_count ≥ 1` (and at most 2000);
  - a delivery address is filled in when `delivery_method == DELIVERY`;
  - the diet notes are at most 500 characters per group.
- `Order.from_cart(customer_id, cart_lines, **details)` builds the order lines from C2's `CartLine`s, **copying today's price** into `unit_price_nok`. The total therefore never changes afterwards.
- `Order.next_statuses` (a property) gives the allowed transitions in a fixed order, used to draw the admin buttons.
- The labels come from the existing `LabelledEnum.label`, for example "In preparation" or "Deposit paid".

## 2 Repository ([order_repository.py](app/models/repositories/order_repository.py))
- `next_order_number() -> str`: `EM-<year>-<NNNN>`, for example `EM-2026-0007`, the year's highest number plus one. It runs inside the same transaction as `add`.
- `search(status=None, date_from=None, date_to=None, customer_id=None) -> list[Order]`: one parameterised query, sorted by event date and then id. It replaces `list_all` and `list_by_customer`, which stay as thin wrappers.
- `update_status` already saves both `status` and `payment_status`, and is reused.
- To show dish names, the controllers use `FoodItemRepository.get_many(ids)` (added in C2). A dish that is part of an order can't be deleted (plan 02), so the name can always be found.
- Customer names for the admin list come from `CustomerRepository.get_many(ids)`, which is new and works like the food item version.

## 3 Controllers
**C3, shop blueprint ([shop.py](app/controllers/shop.py)):** `GET/POST /checkout` with `@login_required`.
- If the cart is empty, it sends the customer back to `/cart` with a message.
- The form asks for:
  - the event type (a select with the `EventCategory` labels);
  - the event date;
  - the delivery method (delivery or pick-up);
  - the delivery address;
  - **guest groups**, each with a label (for example "Main group" or "Vegetarians"), a guest count and allergy/diet notes. Three rows are shown, and an "Add another group" button adds more with a few lines of JavaScript. Without JavaScript the three rows still work. Empty rows are ignored.
- The page also shows a read-only summary of the cart (lines and estimated total), the **total number of guests**, and the hint "Please don't write guests' names in the notes" (the Lab 7 GDPR note).
- On POST:
  - it loads the cart and checks every line again against the minimum order (dishes may have changed);
  - it builds the order with `Order.from_cart` and runs `validate()`;
  - if there are errors, the form is shown again with what the customer typed;
  - on success it calls `OrderRepository.add`, **empties the cart**, shows "Order EM-2026-0001 was sent. Ekte Mat will confirm it.", and redirects to C4's order page.
- The "Continue to order" button in the cart is switched on and links to `/checkout`.

**C4, account blueprint ([account.py](app/controllers/account.py)), all with `@login_required`:**
- `GET /account/orders` lists the customer's **own** orders: order number, event date and type, guests, total, **status** and **payment status** (as coloured labels). It is sorted with the newest event first.
- `GET /account/orders/<id>` shows the order: event details, delivery, guest groups with notes, dish lines with prices and total, and both statuses. **Another customer's order gives 404**, so customers can't guess order ids.
- `/account/` links to "My orders" and shows the newest order.

**A3, admin blueprint ([admin.py](app/controllers/admin.py)), all with `@admin_required`:**
- `GET /admin/orders` lists all orders, with filters from the query string:
  - `status` (All or one `OrderStatus`);
  - `date_from` and `date_to` (date fields);
  - bad values are ignored and a message is shown.
- The columns are order number, event date, customer, event type, guests, total, status and payment status. The filters stay filled in after searching.
- `GET /admin/orders/<id>` shows everything the customer sees, plus the customer's contact details. **Guest groups with allergy or diet notes are highlighted**, which helps the kitchen.
  - **Status:** one button per allowed next status from `order.next_statuses`, for example "Approve", "Reject" and "Cancel" for a submitted order. A delivered, rejected or cancelled order shows "Final status" and no buttons.
  - **Payment status:** a select with all four values and a Save button.
- `POST /admin/orders/<id>/status` calls `order.change_status(new)`. A `ValueError` (an illegal change, for example sent from an old page) shows a red message and changes nothing.
- `POST /admin/orders/<id>/payment` sets `payment_status`.
- The admin dashboard links to Orders and shows the number of **submitted** orders waiting.

## 4 Templates
- `shop/checkout.html` (new): the form, the guest-group rows with the small "Add another group" script, and the cart summary.
- `account/orders.html` and `account/order_detail.html` (new).
- `admin/orders/list.html` and `admin/orders/detail.html` (new).
- `_macros.html`:
  - `status_badge(order)` and `payment_badge(order)`, using CSS classes per value;
  - `order_summary(order, items_by_id)`, the shared table of guest groups and lines used by C4 and A3.
- `base.html`: CSS for the badges and the highlighted notes.
- `shop/cart.html`: switch on the "Continue to order" button.

## 5 Seed ([seed.py](seed.py))
- Replace the single `EM-0001` with **5 demo orders**, numbered by `next_order_number()`, across both test customers. They cover the statuses submitted, approved, in preparation, delivered and cancelled, and the payment statuses not paid, deposit paid, invoiced and paid. They use realistic dates (some past, some future) and guest groups with notes like "2 guests: gluten free" (no names).
- This makes A3's filters and the report screenshots easy to show.

## 6 Tests
- **`test_order_model.py`**:
  - `validate()` catches each error: no lines, the date today or in the past, no groups, a guest count of 0, delivery without an address (pick-up without one is fine), and notes that are too long;
  - `from_cart` copies prices, and a later price change doesn't change the total;
  - `next_statuses` is correct for every status.
- **`test_order_repository.py`**:
  - order numbers count up within a year;
  - `search` filters by status, by date range (inclusive at both ends) and by customer, and combinations of these.
- **`test_checkout.py`** (C3):
  - visitors who aren't logged in are sent to login with `next=/checkout`;
  - an empty cart is sent back to `/cart`;
  - each validation error is shown and the input is kept;
  - success saves the order with the right groups, lines, copied prices and total, empties the cart, and redirects to the order page;
  - a cart line that has fallen below a changed minimum blocks submitting;
  - empty guest rows are ignored.
- **`test_my_orders.py`** (C4):
  - the list shows only the customer's own orders, with both statuses;
  - the detail page works for the owner and gives 404 for another customer;
  - a status changed by the admin is shown to the customer.
- **`test_admin_orders.py`** (A3):
  - only admins can open the pages (403 for customers);
  - the filters work by status, by date range, and both together, and bad filter values are ignored;
  - the detail page shows the notes highlighted;
  - only allowed status buttons are shown;
  - submitted → approved → in preparation → delivered works;
  - an illegal change (submitted → delivered) is refused and nothing changes;
  - rejected and cancelled have no buttons;
  - the payment status is saved.
- **One end-to-end test with CSRF on:** add to cart → log in → checkout → admin approves → customer sees "Approved".

## 7 Docs
- Save this plan to `docs/plans/04-orders.md`.
- README: Features lines for C3, C4 and A3.
- CLAUDE.md: the rule "Order status changes only through `Order.change_status`; prices are copied into `OrderLine.unit_price_nok` when the order is placed."

## Verification
1. `pytest`: all tests pass, the 79 old ones and the new ones.
2. `python seed.py`, then `flask --app app run --debug`:
   - as `private.customer@example.com`: add dishes to the cart, check out with two guest groups (one with "gluten free"), see the order in **My orders** as *Submitted / Not paid*;
   - as `admin@ektemat.example`: **Orders**, filter on *Submitted*, open the new order, see the highlighted notes, click **Approve**, set the payment to *Deposit paid*;
   - back as the customer: the order shows *Approved / Deposit paid*;
   - try the date filter on the demo orders.
