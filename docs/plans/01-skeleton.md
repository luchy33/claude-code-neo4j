# Plan 01 – Project skeleton for Ekte Mat Online (Flask MVC)

## Context
The repo has only Lab 7 material (`labb_claude_cowork/`) and a CLAUDE.md that describes an MVC layout (`app/models`, `app/models/repositories`, `app/controllers`, `app/templates`, `tests/`, `docs/plans/`, `seed.py`) that does not exist yet. This plan creates that skeleton so that Oblig 4 features can be added one at a time. Storage sits behind repository classes, because Oblig 5 replaces SQLite with Neo4j.

Design reference: `labb_claude_cowork/docs/models/` (the user wrote `docs/models/`), mainly `02_uml_domain-class_2026-10-22.puml` and `02_uml_state-machine_order_2026-10-22.puml`. The skeleton uses a **reduced** version of that model. The user's request takes priority where the two differ (see "Deviations from the Lab 7 model").

Status: agreed and implemented 2026-10-26.

## Key decisions
- **Plain `sqlite3`, not SQLAlchemy.** Repositories write SQL and return domain objects. Moving to Neo4j then means writing new repository classes, with no ORM to remove from the models.
- **Domain models are plain `@dataclass`es** with no database code. Status values are `str`-based `Enum`s, so they are stored as readable text.
- **Order status transitions live in the domain**: `Order.ALLOWED_TRANSITIONS` and `Order.change_status(new)`, which raises `ValueError` on an illegal transition. Repositories only save the result.
- **Money is stored as whole NOK in `INTEGER`** columns named `*_nok`.
- **The admin is a `Customer` with `is_admin = 1`.** This is a simplification of the model's separate `StaffUser`. Passwords are hashed with `werkzeug.security`, which ships with Flask. Login itself is **out of scope** for the skeleton, which only stores the fields.
- **The connection is opened once per request** and kept on `flask.g`, then closed in `teardown_appcontext`. The database file is `instance/ektemat.sqlite`, and `instance/` is already in `.gitignore`.

## Files to create
```
requirements.txt            Flask>=3.1,<4 · python-dotenv · pytest
config.py                   Config (SECRET_KEY from env, DATABASE path), TestConfig
.env.example                SECRET_KEY=change-me   (real .env stays ignored)
seed.py
README.md                   (rewrite: description + run commands, Windows + bash)
app/__init__.py             create_app(config_class=Config)
app/models/__init__.py      re-exports domain classes
app/models/enums.py         OrderStatus, PaymentStatus, EventType, DeliveryMethod
app/models/food_item.py     FoodItem
app/models/customer.py      Customer
app/models/order.py         Order, GuestGroup, OrderLine  (+ transition rules)
app/models/question.py      Question
app/models/repositories/__init__.py
app/models/repositories/db.py          get_db(), close_db(), init_db(), `flask init-db` CLI
app/models/repositories/schema.sql
app/models/repositories/food_item_repository.py   (add, get, list_all, list_by_event_type)
app/models/repositories/customer_repository.py    (add, get, get_by_email)
app/models/repositories/order_repository.py       (add with guest groups + lines, get, list_all, update_status)
app/models/repositories/question_repository.py    (add, list_all)
app/controllers/__init__.py
app/controllers/shop.py     bp "shop",    url_prefix "/"      → index: list food items
app/controllers/account.py  bp "account", url_prefix "/account" → placeholder page
app/controllers/admin.py    bp "admin",   url_prefix "/admin"   → placeholder page
app/templates/base.html     layout, nav to the three areas, lang="en-GB"
app/templates/shop/index.html
app/templates/account/index.html
app/templates/admin/index.html
app/static/.gitkeep         (later: food images)
tests/conftest.py           app fixture (TestConfig, tmp_path DB, init_db) + client fixture
tests/test_app.py           the one test
docs/plans/01-skeleton.md   copy of this plan
```
Update CLAUDE.md only if a command changes, for example to add the Windows venv activation line.

## Domain model (fields)
Based on the class diagram and reduced for the skeleton:

- **FoodItem** (the model's `Dish`): `id, name_no, name_en, description, price_per_person_nok, event_type, allergens (comma-separated text for now), image_filename (optional), active`
- **Customer**: `id, name, email (unique), phone?, customer_type ('private'|'corporate'), organisation_number?, password_hash, is_admin, created_at`
- **Order**: `id, order_number (unique), customer_id, event_type, event_date, delivery_method, delivery_address?, status, payment_status, created_at`, plus `guest_groups: list[GuestGroup]` and `lines: list[OrderLine]`. It also has a `total_nok` property.
- **GuestGroup**: `id, order_id, label?, guest_count (>0), diet_notes?`
- **OrderLine**: `id, order_id, food_item_id, quantity (>0), unit_price_nok`. The price is copied in when the order is placed, so later price changes don't alter old orders.
- **Question** (not in the UML; comes from the shop and admin requirement): `id, customer_id?, name, email, subject, body, answer?, created_at, answered_at?`

**Enums**
- `OrderStatus`: `submitted, approved, in_preparation, delivered, rejected, cancelled`
- `PaymentStatus`: `not_paid, deposit_paid, invoiced, paid`
- `EventType`: `lunch_meeting, party, wedding_dinner, other` (from the model)
- `DeliveryMethod`: `delivery, pick_up`

**Order transitions**
```
submitted      → approved | rejected | cancelled
approved       → in_preparation | cancelled
in_preparation → delivered
delivered, rejected, cancelled → (final)
```
Payment status is set freely in the skeleton. Its rules (for example, whether a deposit is required before approval) belong to a later plan.

`schema.sql` enforces the same rules with `CHECK (status IN (...))`, `CHECK (quantity > 0)` and `CHECK (guest_count > 0)`, with `FOREIGN KEY`s and `PRAGMA foreign_keys = ON` set in `get_db()`. Guest groups and order lines use `ON DELETE CASCADE`, matching the model's composition.

## Deviations from the Lab 7 model
I'll record these in `docs/plans/01-skeleton.md` so the traceability gap is visible:
- The model's `REQUESTED/AWAITING_DEPOSIT/CONFIRMED/INVOICED` statuses become `submitted/approved`. Deposit and invoicing move to the separate `payment_status`.
- These are left out for later: PrivateCustomer/CorporateCustomer subclasses (replaced by `customer_type`), CompanyUser, Menu, Allergen and Ingredient tables, Supplier, StaffUser, StandingOrder, Invoice, Payment, CapacityLimit, AllergyConfirmation and DataSubjectRequest.

## Seed script (`python seed.py`)
1. Calls `create_app()`, then in the app context runs `init_db()` (drop and recreate, with a warning printed).
2. Adds about 8 synthetic food items spread across the event types. Names and prices follow `labb_claude_cowork/docs/04_Data/04_reference_lunch-menu-autumn_2026-10-20.txt` (read it when implementing).
3. Adds one admin (`admin@ektemat.example`) and two test customers: one private and one corporate with a made-up organisation number, all on `@example.com`. Passwords come from `SEED_PASSWORD` in `.env` and fall back to a printed dev default.
4. Optionally adds one sample order with a guest group and lines, so the admin page has something to show later.

## The one test
`tests/test_app.py::test_shop_index_lists_food_items`: insert one FoodItem through `FoodItemRepository` into the temporary database, `GET /`, and assert status 200 and that the item's name appears in the page. This one test covers the app factory, blueprint registration, the repository, the schema and the template.

## README
A short description, the setup commands for Windows PowerShell (`.venv\Scripts\Activate.ps1`) and bash, then `pip install -r requirements.txt`, `copy .env.example .env`, `python seed.py`, `flask --app app run` and `pytest`. It also links to CLAUDE.md and `docs/plans/`. The current two-line README is replaced.

## Verification
1. `python -m venv .venv`, activate it, then `pip install -r requirements.txt`
2. `python seed.py`: prints the counts (8 food items, 3 customers)
3. `flask --app app run`: `/` lists the seeded food items, and `/account` and `/admin` render their placeholders
4. `pytest`: 1 passed
5. `python -c "from app.models import Order; ..."`: a quick check that `submitted → delivered` raises `ValueError` (I'll do this by hand; it won't be added as a test, since the request asks for exactly one test)
