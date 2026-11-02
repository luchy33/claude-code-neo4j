# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Ekte Mat Online

Ekte Mat Online is the ordering system for Ekte Mat AS, a (fictional) catering company in Bergen, replacing orders by e-mail, phone and Excel.

It has a customer shop (menu by event, cart, orders, questions) and an admin panel (food items, images, orders, questions), built in Flask for INFO212 Oblig 4.

## MVC layout

- `app/models/` – domain classes (FoodItem, Order, OrderLine, Customer, Question …) and repositories
- `app/models/repositories/` – the only code that touches storage: SQLite now (Neo4j in Oblig 5), image files (`ImageStore`) and the session cart (`SessionCartRepository`)
- `app/models/services/` – external services: the Claude image generator (`claude-opus-5-5`, draws SVG)
- `app/controllers/` – Flask blueprints: `shop`, `account`, `admin`; `auth.py` has login/admin decorators and CSRF
- `app/templates/` – Jinja2 views, one folder per blueprint
- `docs/plans/` – agreed plans for larger features
- `labb_claude_cowork/` – Lab 7 requirements and models (read-only source material)

## Commands

```bash
python -m venv .venv && source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed.py               # resets DB + uploads: synthetic food items, one admin, test customers
flask --app app run          # http://127.0.0.1:5000
pytest
```

## Rules

- Only repository classes touch the database; controllers and views never do.
- Every feature has pytest tests in `tests/`.
- Larger features start in plan mode; the agreed plan is saved in `docs/plans/`.
- Never commit secrets or API keys; use `.env` (listed in `.gitignore`).
- Tests never call the Claude API; they use `FakeImageGenerator` (`IMAGE_GENERATOR=fake`).
- Every POST form includes `csrf_token()`; admin routes use `@admin_required`.
- Generated or uploaded images are untrusted: SVG only via `sanitise_svg`, served only through `image_response`.
- The cart lives in the session and holds only item ids and quantities; prices always come from `FoodItemRepository`. Minimum-order rules live in `Cart` (`app/models/cart.py`).
- Order status changes only through `Order.change_status` (allowed transitions in `Order.ALLOWED_TRANSITIONS`); prices are copied into `OrderLine.unit_price_nok` when the order is placed.
- Synthetic data only.
- Use British English in code, comments and UI text.
- All prices are in NOK.
- Questions always belong to an order; customers only see questions on their own orders.
