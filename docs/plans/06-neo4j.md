# Plan 06 – Replace SQLite with Neo4j

Status: agreed 2026-11-02.

## Context
CLAUDE.md and plan 01 say Oblig 5 replaces SQLite with Neo4j. The repositories were designed for this switch: only `app/models/repositories/` touches storage, and controllers and templates never do. The user chose:
- **Replace SQLite entirely.** Neo4j is the only database, and `sqlite3` and `schema.sql` are removed.
- **Run Neo4j with Docker** using a `docker-compose.yml` in the repo.
- **Run tests against a real Neo4j test database** and skip them with a clear message when it isn't reachable.

Controllers, templates, domain models, `ImageStore` and `SessionCartRepository` don't change. The repositories keep the same public methods and return the same domain objects, so the existing tests should pass once the fixtures are updated. At implementation time this plan is copied to `docs/plans/06-neo4j.md`, following the CLAUDE.md rule.

## 1 Infrastructure
- **`requirements.txt`**: add the official `neo4j` Python driver, pinned to a current major version.
- **`docker-compose.yml`** (new), with two services on the `neo4j:5.26` LTS image:
  - `neo4j`: the dev database. Ports 7474 (browser) and 7687 (bolt), a named volume, and `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`, which Compose reads from `.env`.
  - `neo4j-test`: the test database. Bolt on port **7688**, no volume (`tmpfs`), and a fixed local-only password `ektemat-test`.
  - This is needed because Neo4j Community allows only one user database. A separate container means pytest never wipes the dev data.
- **`config.py`**:
  - Remove `DATABASE`.
  - Add `NEO4J_URI` (default `bolt://localhost:7687`), `NEO4J_USER` (`neo4j`), `NEO4J_PASSWORD` and `NEO4J_DATABASE` (`neo4j`).
  - `TestConfig` reads `TEST_NEO4J_URI` (default `bolt://localhost:7688`) and `TEST_NEO4J_PASSWORD` (default `ektemat-test`).
- **`.env.example`**: add `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD=change-me-min-8-chars` (Neo4j 5 requires at least 8 characters).
- **`app/__init__.py`**: drop `DATABASE` from the instance-path loop, which leaves only `UPLOAD_FOLDER`. `db.init_app(app)` is still called.

## 2 Connection module: `app/models/repositories/db.py` (rewritten)
This is still the only module the repositories import for storage.
- `init_app(app)` creates one `neo4j.GraphDatabase.driver(...)` per app and stores it in `app.extensions["neo4j"]`. The driver connects lazily. It also registers the `init-db` CLI command, keeping the same name as before.
- `query(cypher, **params) -> list[Record]` is for reads and single-statement writes. It uses `driver.execute_query(..., database_=NEO4J_DATABASE)`.
- `write(fn)` runs `fn(tx)` inside `session.execute_write`. It is used where several statements must form one transaction: new ids plus an order with its lines.
- `next_ids(tx, label, n=1) -> list[int]` keeps an integer id per label on a `(:Counter {name})` node, using `SET c.value = coalesce(c.value, 0) + $n`. The domain, URLs and session cart keep using `int` ids. Neo4j's `elementId` is not used.
- `init_db()` deletes all data (`MATCH (n) DETACH DELETE n`), then runs `schema.cypher`, which is idempotent (`IF NOT EXISTS`):
  - uniqueness constraints on `id` for every label;
  - uniqueness constraints on `Customer.email`, `Customer.organisation_number` and `Order.order_number`;
  - then `init_db()` `MERGE`s the fixed value nodes (`EventCategory`, `Allergen`, `DietaryLabel`) from the Python enums (`VALUE_NODES` in `db.py`).
- `close_driver(app)` is used by test teardown.
- `app/models/repositories/schema.sql` is replaced by **`schema.cypher`**.

## 3 Graph model
Foreign keys become relationships, and the value-set join tables become shared value nodes. The `schema.sql` comment already anticipated this.

```
(:FoodItem {id, name_en, name_no, description, price_nok, min_order_quantity, image_filename, published})
   -[:SUITABLE_FOR]->(:EventCategory {value})
   -[:CONTAINS]->(:Allergen {value})
   -[:HAS_LABEL]->(:DietaryLabel {value})
(:Customer {id, name, email, phone, customer_type, organisation_number, password_hash, is_admin, created_at})
   -[:PLACED]->(:Order {id, order_number, event_date, delivery_method, delivery_address, status, payment_status, created_at})
(:Order)-[:FOR_EVENT]->(:EventCategory)
(:Order)-[:HAS_GUEST_GROUP]->(:GuestGroup {id, label, guest_count, diet_notes})
(:Order)-[:HAS_LINE]->(:OrderLine {id, quantity, unit_price_nok})-[:OF_ITEM]->(:FoodItem)
(:Question {id, name, email, subject, body, answer, created_at, answered_at})-[:ABOUT]->(:Order)
(:Customer)-[:ASKED]->(:Question)            // optional, like the nullable customer_id
```

- Dates and datetimes are stored as native Neo4j `date` and `localdatetime` values. A small helper in `db.py` converts them back with `.to_native()`.
- Enums are stored as their `.value` strings.
- `customer_id`, `order_id` and `food_item_id` on the domain objects are read from the relationships, using `RETURN c.id AS customer_id`.

## 4 Repositories (same public API, Cypher inside)
| File | Notes |
|---|---|
| `customer_repository.py` | Straightforward conversion. `get_many` uses `WHERE c.id IN $ids`. |
| `food_item_repository.py` | `add`/`update` write the node and re-link its value nodes in one query (delete the old `SUITABLE_FOR`/`CONTAINS`/`HAS_LABEL` relationships, then `UNWIND` + `MATCH` + `MERGE`). Reads collect the three value sets with `COLLECT` in the same query, which avoids the current N+1 queries. `delete` raises `FoodItemInUseError` if `(:OrderLine)-[:OF_ITEM]->(f)` exists, and otherwise runs `DETACH DELETE`. `list_by_category` matches `(f)-[:SUITABLE_FOR]->(:EventCategory {value})`. |
| `order_repository.py` | `add` runs as one `write()` transaction: allocate ids, create the order, `PLACED`, `FOR_EVENT`, guest groups and lines (with `OF_ITEM`), and set the domain ids. `next_order_number` keeps the `EM-YYYY-NNNN` format using `max(toInteger(substring(...)))`; the unique constraint guards against duplicates. `search` builds a `WHERE` with the same optional filters and ordering. `_to_order` loads groups and lines in the same query (`COLLECT`). |
| `question_repository.py` | `search` orders unanswered first with `ORDER BY q.answer IS NOT NULL, q.created_at DESC, q.id DESC`. `count_by_order` uses `count(q)` and `sum(CASE WHEN q.answer IS NULL THEN 1 ELSE 0 END)`. |

The Cypher is parameterised everywhere. Only fixed identifiers, such as the relationship type taken from `VALUE_SETS`, are ever formatted into a query string.

## 5 seed.py
- No logic changes: it already uses only repositories and `init_db()`.
- Update the printed message to name the Neo4j URI instead of the SQLite path.
- Give a friendly error if Neo4j isn't reachable ("Start it with `docker compose up -d neo4j`").

## 6 Tests
- **`tests/conftest.py`**:
  - A session-scoped `neo4j_available` fixture tries `verify_connectivity()` on the test URI. On failure it calls `pytest.skip("Neo4j test database not reachable – run: docker compose up -d neo4j-test")`.
  - A `make_app(**overrides)` factory fixture builds `create_app(TestConfig, UPLOAD_FOLDER=tmp_path/..., **overrides)`, runs `init_db()` and closes the driver at teardown.
  - A safety guard refuses to run if the test URI equals `NEO4J_URI`, so the dev data can never be wiped.
  - The `app` fixture uses `make_app()`.
  - Pure model tests (`test_cart_model`, `test_order_model`, `test_question_model`) don't use `app`, so they still run without Neo4j.
- The four CSRF/e2e tests that build their own app (`test_auth.py`, `test_cart.py`, `test_admin_orders.py`, `test_questions.py`) switch from `DATABASE=...sqlite` + `init_db()` to `make_app(CSRF_ENABLED=True)`.
- **New `tests/test_neo4j_repositories.py`** covers:
  - the graph structure: an order creates the `PLACED`, `HAS_LINE`→`OF_ITEM` and `ABOUT` relationships, and food item value sets become value-node relationships;
  - id counters increase and stay unique;
  - unique constraints reject a duplicate e-mail;
  - `init_db` is idempotent.
- `tests/test_order_repository.py` already exercises `next_order_number`, `search` and `count_by_status`, so it serves as the regression suite.

## 7 Docs
- **README**: in Getting started, add `docker compose up -d` before `python seed.py`. Mention the Neo4j Browser at http://localhost:7474. Replace the SQLite file sentence and "after pulling a change to schema.sql" with `schema.cypher`.
- **CLAUDE.md**:
  - Change "SQLite now (Neo4j in Oblig 5)" to "Neo4j".
  - Add `docker compose up -d` to Commands.
  - Add the rule "tests use the separate `neo4j-test` container (port 7688), never the dev database".
- Save this plan as `docs/plans/06-neo4j.md`.

## Changes during implementation
- `NEO4J_PASSWORD` has a local dev default (`ektemat-dev-db`) in both `config.py` and `docker-compose.yml`, like `SECRET_KEY` and `SEED_PASSWORD`. Without it, Compose refuses to start any service until `.env` has a password.
- `db.verify_connection()` lets `seed.py` fail at once when Neo4j is down, instead of after the driver's ~30 s of retries.
- The driver is v6 (`neo4j>=6.0,<7`), and the server image is `neo4j:5.26`.

## Verification
1. `docker compose up -d`, then `pip install -r requirements.txt`.
2. `pytest`: the whole suite passes against `neo4j-test`. Stop the test container and run `pytest` again: the DB tests are skipped with the message, and the model tests still pass.
3. `python seed.py`, then `flask --app app run`. Click through the menu by event, cart → checkout, My orders, asking a question, the admin food item edit/picture, order status change and answering a question.
4. In Neo4j Browser (http://localhost:7474), run `MATCH p=(:Customer)-[:PLACED]->(:Order)-[:HAS_LINE]->()-[:OF_ITEM]->() RETURN p` to see the seeded graph.
