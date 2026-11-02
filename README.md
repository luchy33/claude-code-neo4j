# Ekte Mat Online

Ordering system for Ekte Mat AS, a fictional catering company in Bergen. It replaces orders by e-mail, phone and Excel. Built with Flask (MVC) for INFO212 Oblig 4. All data is synthetic.

- **Shop**: menu cards grouped by event (C1) and a shopping cart with an estimated total; quantities below a dish's minimum order are refused (C2). Logged-in customers send the order with event date, delivery and guest groups with allergy notes (C3).
- **Account**: register, log in and log out (customers and admins share one login page); *My orders* shows each order with its status and payment status (C4). On an order's page the customer asks questions about that order and reads Ekte Mat's answers (C5).
- **Admin**: add, edit and remove food items (A1), and upload or AI-generate their pictures with a preview before saving (A2). Orders can be filtered by status and event date, and each order's status and payment status is managed on its own page (A3). Customers' questions are listed with the unanswered ones first and answered (or the answer changed) from their own page (A4).

## Getting started

Requires Python 3.10 or newer.

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then edit SECRET_KEY and SEED_PASSWORD
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
python seed.py
flask --app app run
pytest
```

`flask --app app init-db` creates empty tables without seed data. The SQLite file is `instance/ektemat.sqlite`.

Seeded accounts: `admin@ektemat.example` (admin), `private.customer@example.com` and `lunch@corporate.example.com`. They all use the password set in `SEED_PASSWORD` (default `ektemat-dev`). `python seed.py` also deletes uploaded pictures, attaches the team's dish pictures from `seed_data/images/` and creates 5 demo orders covering every order and payment status, plus 3 demo questions (1 answered).

**After pulling a change to `app/models/repositories/schema.sql`, run `python seed.py` again.** There are no migrations, so an old database gives errors (for example, questions need the `order_id` column added in plan 05).

### AI-generated pictures (A2)

On a food item's *Picture* page the admin can write an instruction, and Claude (`claude-opus-5-5`) draws an SVG illustration, or changes the current picture. The result is shown as a preview and is only stored when the admin clicks *Save*.

- Put your key in `.env`: `ANTHROPIC_API_KEY=...`. **Never commit it.** `.env` is in `.gitignore`.
- Each picture costs roughly 1–3 NOK in API usage.
- To work without a key, set `IMAGE_GENERATOR=fake` in `.env`. You then get an offline placeholder picture. The tests always use the fake generator and never call the API.
- Generated SVG is checked against an allowlist (no scripts, styles, event handlers or external links) before it is shown.

## Structure

- `app/models/`: domain classes (dataclasses, no database code)
- `app/models/repositories/`: the only code that touches storage (SQLite database and image files)
- `app/models/services/`: external services (the Claude image generator)
- `app/controllers/`: blueprints `shop`, `account` and `admin`
- `app/templates/`: Jinja2 views, one folder per blueprint
- `tests/`: pytest
- `docs/plans/`: agreed feature plans, [01-skeleton.md](docs/plans/01-skeleton.md), [02-auth-and-food-items.md](docs/plans/02-auth-and-food-items.md), [03-menu-and-cart.md](docs/plans/03-menu-and-cart.md), [04-orders.md](docs/plans/04-orders.md)
- `labb_claude_cowork/`: Lab 7 requirements and models (read-only)

See [CLAUDE.md](CLAUDE.md) for the project rules.
