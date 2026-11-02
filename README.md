# Ekte Mat Online

Ordering system for Ekte Mat AS, a fictional catering company in Bergen. It replaces orders by e-mail, phone and Excel. Built with Flask (MVC) for INFO212 Oblig 4. All data is synthetic.

- **Shop**: menu cards grouped by event (C1) and a shopping cart with an estimated total; quantities below a dish's minimum order are refused (C2). Logged-in customers send the order with event date, delivery and guest groups with allergy notes (C3).
- **Account**: register, log in and log out (customers and admins share one login page); *My orders* shows each order with its status and payment status (C4). On an order's page the customer asks questions about that order and reads Ekte Mat's answers (C5).
- **Admin**: add, edit and remove food items (A1), and upload or AI-generate their pictures with a preview before saving (A2). Orders can be filtered by status and event date, and each order's status and payment status is managed on its own page (A3). Customers' questions are listed with the unanswered ones first and answered (or the answer changed) from their own page (A4).

## Getting started

Requires Python 3.10 or newer and Docker (for the Neo4j database).

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then edit SECRET_KEY, SEED_PASSWORD and NEO4J_PASSWORD
docker compose up -d        # starts Neo4j (dev) and a separate Neo4j for the tests
python seed.py              # resets the database with synthetic data
flask --app app run         # http://127.0.0.1:5000
pytest
```

**macOS / Linux / Git Bash**
```bash
python -m venv .venv
source .venv/bin/activate   # Git Bash on Windows: source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d
python seed.py
flask --app app run
pytest
```

`flask --app app init-db` empties the database and creates the constraints without seed data.

### Neo4j

The data lives in Neo4j 5, started by `docker compose up -d` ([docker-compose.yml](docker-compose.yml)):

- `neo4j` is the dev database: bolt on `bolt://localhost:7687`, and Neo4j Browser at http://localhost:7474 (user `neo4j`, password `NEO4J_PASSWORD` from `.env`, default `ektemat-dev-db`). Its data is kept in a Docker volume.
- `neo4j-test` is used only by `pytest`, on port 7688. Every test empties it. If it is not running, the database tests are skipped with a hint.

The graph model is in [schema.cypher](app/models/repositories/schema.cypher) and [docs/plans/06-neo4j.md](docs/plans/06-neo4j.md). Try this in Neo4j Browser:

```cypher
MATCH p=(:Customer)-[:PLACED]->(:Order)-[:HAS_LINE]->(:OrderLine)-[:OF_ITEM]->(:FoodItem) RETURN p
```

If you change `NEO4J_PASSWORD` after the first start, run `docker compose down -v` once (this deletes the dev data), then `docker compose up -d` and `python seed.py`.

Seeded accounts: `admin@ektemat.example` (admin), `private.customer@example.com` and `lunch@corporate.example.com`. They all use the password set in `SEED_PASSWORD` (default `ektemat-dev`). `python seed.py` also deletes uploaded pictures, attaches the team's dish pictures from `seed_data/images/` and creates 5 demo orders covering every order and payment status, plus 3 demo questions (1 answered).

**After pulling a change to the repositories or `app/models/repositories/schema.cypher`, run `python seed.py` again.** There are no migrations.

### AI-generated pictures (A2)

On a food item's *Picture* page the admin can write an instruction, and Claude (`claude-opus-5-5`) draws an SVG illustration, or changes the current picture. The result is shown as a preview and is only stored when the admin clicks *Save*.

- Put your key in `.env`: `ANTHROPIC_API_KEY=...`. **Never commit it.** `.env` is in `.gitignore`.
- Each picture costs roughly 1–3 NOK in API usage.
- To work without a key, set `IMAGE_GENERATOR=fake` in `.env`. You then get an offline placeholder picture. The tests always use the fake generator and never call the API.
- Generated SVG is checked against an allowlist (no scripts, styles, event handlers or external links) before it is shown.

## Structure

- `app/models/`: domain classes (dataclasses, no database code)
- `app/models/repositories/`: the only code that touches storage (Neo4j database and image files)
- `app/models/services/`: external services (the Claude image generator)
- `app/controllers/`: blueprints `shop`, `account` and `admin`
- `app/templates/`: Jinja2 views, one folder per blueprint
- `tests/`: pytest
- `docs/plans/`: agreed feature plans, [01-skeleton.md](docs/plans/01-skeleton.md), [02-auth-and-food-items.md](docs/plans/02-auth-and-food-items.md), [03-menu-and-cart.md](docs/plans/03-menu-and-cart.md), [04-orders.md](docs/plans/04-orders.md), [05-questions.md](docs/plans/05-questions.md), [06-neo4j.md](docs/plans/06-neo4j.md)
- `labb_claude_cowork/`: Lab 7 requirements and models (read-only)

See [CLAUDE.md](CLAUDE.md) for the project rules.
