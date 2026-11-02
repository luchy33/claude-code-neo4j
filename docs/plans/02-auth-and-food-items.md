# Plan 02 – Auth (customer + admin) and food items with images (A1, A2)

Status: agreed 2026-10-26.

## Context
Plan 01 built the skeleton, with placeholder `account` and `admin` pages and no login. Oblig 4 needs:
- **A1 Food items.** The admin can add, edit and remove items with these fields: name, description, price in NOK, minimum order quantity, event categories, allergens and dietary labels, and a published flag.
- **A2 Images.** The admin can upload a picture **or** write an instruction for an AI to create or modify one, and **previews the result before it is saved**.
- **C3 needs login or registration**, and the admin panel must be closed to everyone except staff.

Decisions agreed with the user:
- Login uses the Flask session with no extra library, and one shared login page.
- A2 covers both upload and AI instruction.
- The AI service is **Claude, which draws SVG pictures**.

Everything still follows CLAUDE.md:
- Only repository classes touch storage. Here that means the database **and image files**.
- Controllers stay thin.
- British English throughout, prices in NOK, synthetic data only, and tests for every feature.

## 1 Model changes (`app/models/`)
**`enums.py`**
- Replace `EventType` with **`EventCategory`**: `birthday, confirmation, wedding, conference, christmas_party, lunch_meeting, other`. These come from the assignment's C1 list plus Lab 7's lunch meetings. `Order.event_type` uses the same enum.
- Add **`Allergen`**: the 14 EU allergens (gluten, crustaceans, eggs, fish, peanuts, soybeans, milk, nuts, celery, mustard, sesame, sulphites, lupin, molluscs). Each value has a `label` property that gives display text.
- Add **`DietaryLabel`**: `vegetarian, vegan, gluten_free, lactose_free`.

**`food_item.py`**: the fields become
`name_en, name_no, description, price_nok (per portion), min_order_quantity (≥1), categories: set[EventCategory] (≥1), allergens: set[Allergen], dietary_labels: set[DietaryLabel], image_filename?, published, id?`
- `price_per_person_nok` is renamed to `price_nok`, and `active` to `published`.
- `validate() -> list[str]` checks that both names are filled in, the price is ≥ 0, the minimum quantity is ≥ 1 and at least one category is chosen.

**`customer.py`**: add `validate_registration(password, confirm) -> list[str]`. It checks that the name is filled in, the e-mail looks valid, the password has at least 8 characters and matches the confirmation, and that a corporate customer has a 9-digit organisation number. `set_password` and `check_password` stay as they are.

**`errors.py` (new)**:
- `FoodItemInUseError`: deleting an item that existing orders refer to.
- `ImageError`: a rejected file or a failed generation, with a message the user can read.

**`services/image_generator.py` (new, model layer, as it is external data access)**:
- `ImageGenerator` protocol: `generate(instruction, current: bytes|None, current_type: str|None) -> bytes` (SVG).
- **`ClaudeImageGenerator`**: uses the `anthropic` SDK with
  `client.beta.messages.create(model="claude-opus-5-5", max_tokens=16000, betas=["server-side-fallback-2026-07-01"], fallbacks="default", output_config={"effort": "medium"}, system=…, messages=…)`.
  - The fallback means a request that is refused on safety grounds is retried on another model automatically.
  - The client is created with `timeout=120, max_retries=1`, because the call happens during a web request.
  - **Modify**: if the item already has an SVG, its text goes with the instruction. If it has a photo, the photo is sent as an image block and Claude draws an SVG illustration based on it.
  - **Errors**: a `stop_reason` of `refusal` or `max_tokens`, `AuthenticationError`, `RateLimitError`, `APIConnectionError` or `APIStatusError` all become an `ImageError` with a clear message.
  - The client can be passed in, so tests can use a stub.
- **`FakeImageGenerator`**: returns a fixed, valid SVG containing the instruction text. It is used by tests and by `IMAGE_GENERATOR=fake`.
- **`sanitise_svg(bytes) -> bytes`**: the SVG Claude returns is treated as untrusted. The function rejects anything over 200 KB and any `DOCTYPE` or `ENTITY`. It parses the file with ElementTree and only allows known shape, text and gradient tags. It rejects `<script>`, `<style>`, `<foreignObject>`, attributes starting with `on…`, and any `href` that doesn't start with `#`.

## 2 Repositories (`app/models/repositories/`)
**`schema.sql`**:
- `food_item` gets the new columns: `price_nok`, `min_order_quantity CHECK ≥1` and `published`.
- New join tables `food_item_category`, `food_item_allergen` and `food_item_dietary_label` link items to their categories, allergens and labels. Each has the columns `(food_item_id REFERENCES … ON DELETE CASCADE, value TEXT CHECK IN (...))` and a composite primary key.
- `customer_order.event_type` CHECK now uses the new category values.

**`food_item_repository.py`**:
- `add` and `update` write the row and the three join tables in one transaction.
- `get`, `list_all(published_only)` and `list_by_category` load the sets back.
- `delete` raises `FoodItemInUseError` if an `order_line` refers to the item.
- `set_image(item_id, filename)` saves the image filename on the item.

**`image_store.py` (new)**: the only code that touches image files. They are stored under `instance/uploads/` (`instance/` is already ignored by git).
- `save_pending(data, ext) -> token` writes `pending/<uuid>.<ext>`.
- `pending_path(token)` validates the token against a pattern before returning the path.
- `promote(token, item_id) -> filename` moves the file to `food/<item_id>-<uuid>.<ext>`.
- `discard(token)` and `delete(filename)` remove files.
- `validate_upload(file)` checks the extension (jpg, jpeg, png or webp) **and** the magic bytes. **SVG uploads are not accepted**; SVGs only come from the generator, after sanitising.

## 3 Controllers (`app/controllers/`)
**`auth.py` (new helpers, not a blueprint)**:
- A `before_app_request` hook loads `g.user` from `session["customer_id"]`.
- `@login_required` redirects to the login page with `?next=`.
- `@admin_required` sends visitors who aren't logged in to the login page and returns **403** for a logged-in non-admin.
- **CSRF**: each session gets a random token. Every form includes it, and every POST that lacks it is refused with 400. This is switched off in `TestConfig`, except in one test that checks it works.

**`account.py`**:
- `GET/POST /account/register`: on success, logs the customer in and sends them to `/account/`.
- `GET/POST /account/login`: calls `session.clear()` before setting the id, to prevent session fixation. Admins land on `/admin/`. Others land on `next`, but only if it's a local path, otherwise on `/account/`.
- `POST /account/logout`.
- `GET /account/` (login required): shows the customer's details. The order list comes later with C4.

**`admin.py`** (every route uses `@admin_required`):
- `/admin/`: dashboard with links.
- `/admin/food-items`: table of all items, with published and unpublished status.
- `/admin/food-items/new` and `/<id>/edit` (GET/POST): the form re-renders with the `validate()` errors.
- `POST /<id>/delete`: on `FoodItemInUseError`, shows a message suggesting to unpublish the item instead.
- `/admin/food-items/<id>/image` (GET): shows the current image, the upload form and the AI instruction form.
- `POST …/image/upload` and `POST …/image/generate`: create a pending image, store `session["pending_image"] = {item_id, token}`, then redirect to the preview.
- `GET …/image/preview`: shows the current and the new image side by side, with **Save** and **Discard** buttons, plus "Refine with new instruction", which modifies the pending image.
- `POST …/image/save` and `…/image/discard`.
- `GET /admin/images/pending/<token>`: serves a pending image to admins only.

**`shop.py`**:
- `/` shows published items as cards grouped by `EventCategory`. Each card has the picture (or a placeholder), the price, the minimum order and the allergens. This is a basic C1, needed because the model changes; cart and filtering come later.
- `GET /images/<filename>` serves saved images.

Both image routes send `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'` and `X-Content-Type-Options: nosniff`, and the pages show images only through `<img>`.

`app/__init__.py`:
- reads `UPLOAD_FOLDER` (default `instance/uploads`), `MAX_CONTENT_LENGTH = 5 MB` and `IMAGE_GENERATOR` (`claude` or `fake`);
- builds the generator once and keeps it in `app.extensions["image_generator"]`;
- registers the auth hooks and adds a `csrf_token()` function for templates;
- `config.py` sets `SESSION_COOKIE_SAMESITE="Lax"`.

## 4 Templates (`app/templates/`)
- `base.html`: the nav shows Log in / Register, or the user's name with a Log out button (a POST form). The Admin link is shown to admins only. Flash messages appear at the top. Some simple card and form CSS is added.
- `account/register.html`, `account/login.html`, `account/index.html`
- `admin/index.html`, `admin/food_items/list.html`, `admin/food_items/form.html` (checkbox groups for categories, allergens and labels), `admin/food_items/image.html`, `admin/food_items/image_preview.html`
- `shop/index.html` (cards)

## 5 Seed, config and docs
- `requirements.txt`: add `anthropic`.
- `.env.example`: add `ANTHROPIC_API_KEY=` (left empty) and `IMAGE_GENERATOR=claude`. The real `.env` is never committed, as the assignment requires.
- `seed.py`: update to the new fields. Each of the 8 items gets categories, allergens, labels and a minimum quantity. No images are seeded, so the cards show a placeholder.
- README: add the image-generation setup, its approximate cost (a few NOK per image with Opus 5.5) and how to run without a key (`IMAGE_GENERATOR=fake`).
- CLAUDE.md: add the rule "Tests never call the Claude API; use `FakeImageGenerator`."
- Save this plan to `docs/plans/02-auth-and-food-items.md`.
- Schema change: run `python seed.py` again after pulling. It rebuilds the database.

## 6 Tests (`tests/`, all offline)
`conftest.py` uses `tmp_path` for the database and uploads, `IMAGE_GENERATOR="fake"` and CSRF off. It provides `customer` and `admin` fixtures and a `login(client, email, pw)` helper.
- **`test_auth.py`**:
  - registration works and logs the customer in;
  - a duplicate e-mail, a short password and a corporate customer without an organisation number are rejected;
  - a wrong password fails;
  - logout clears the session;
  - `/admin/` redirects visitors who aren't logged in, gives 403 to a customer and 200 to an admin;
  - an outside `next` URL is ignored;
  - a POST without a CSRF token gets 400 when CSRF is on.
- **`test_food_items.py`**:
  - the repository saves and reloads categories, allergens and labels correctly;
  - `validate()` catches each error;
  - an admin can create and edit an item, and the changes appear in the shop;
  - an unpublished item is hidden from the shop;
  - delete works, and deleting an item that orders use is blocked.
- **`test_images.py`**:
  - uploading a PNG goes to the preview and the item is not changed yet;
  - Save sets `image_filename`, writes the file and serves it at `/images/…` with the CSP header;
  - Discard deletes the pending file;
  - a `.exe`, a fake PNG and an SVG upload are rejected;
  - a file over 5 MB gets 413;
  - the fake generator goes to the preview and Save stores the SVG;
  - `sanitise_svg` rejects script, `onload`, `foreignObject` and external `href`;
  - `ClaudeImageGenerator` with a stub client builds the right request, pulls the SVG out of the reply and turns a refusal into `ImageError`.
- **`test_app.py`**: updated for the new fields.

## Verification
1. `pip install -r requirements.txt`, `python seed.py`, then `pytest`. All tests should pass.
2. `flask --app app run`, then check by hand:
   - register a new customer, log out, and log in again;
   - `/admin` is refused for that customer;
   - log in as `admin@ektemat.example` and add a food item;
   - upload a picture, preview it and save it;
   - check that the item's card in the shop shows the image, price, minimum order and allergens.
3. With `ANTHROPIC_API_KEY` set, generate a picture once from an instruction, preview it, refine it once and save it. I'll ask before running this, because it costs money.
4. Before committing, check with `git status` that no `.env` or `instance/` files are staged.
