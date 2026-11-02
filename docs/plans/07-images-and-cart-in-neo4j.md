# Plan 07 – Store pictures and the shopping cart in Neo4j

Status: agreed 2026-11-02.

## Context
Plan 06 moved all records to Neo4j, but two things still live elsewhere:
- **Food pictures** are files under `instance/uploads/`, written by `ImageStore`.
- **The shopping cart** lives in the session cookie, written by `SessionCartRepository`.

The user wants both in Neo4j, with the cart **linked to the customer** after login. A customer's cart then survives logout and comes back on their next login, on any device.

Controllers keep calling the same repository methods, so the change stays inside `app/models/repositories/` plus small edits to `auth.py` and the fixtures. At implementation time this plan is saved as `docs/plans/07-images-and-cart-in-neo4j.md`.

## 1 Graph additions
```
(:Image {name, data: bytes, pending: bool, created_at})
(:FoodItem)-[:HAS_IMAGE]->(:Image)                      // the saved front picture
(:Cart {token, updated_at})-[:HAS_ITEM {quantity}]->(:FoodItem)
(:Customer)-[:HAS_CART]->(:Cart)                         // a logged-in customer's cart
```
In `schema.cypher`, add unique constraints on `Image.name` and `Cart.token`.

## 2 Pictures: `image_store.py` keeps its API, and the bytes go into Neo4j
- `ImageStore()` takes no folder argument any more. Its methods and their behaviour stay the same:
  - `validate_upload` (unchanged), `mime_type`, `save_pending`, `read_pending`, `promote`, `discard`, `read_food` and `delete`.
  - `TOKEN_RE`/`FILENAME_RE` stay, so names are still random and checked before any query.
- `save_pending(data, ext)` creates `(:Image {name: token, data, pending: true, created_at})`. It also deletes pending images older than one day; abandoned previews used to stay on disk forever.
- `read_pending` gives the same errors as before: "Unknown image." for a bad name, and "The preview has expired…" when no pending image has that name.
- `promote(token, item_id)` renames the node to `<item_id>-<uuid>.<ext>` and sets `pending = false`. Both happen in one statement.
- `discard` and `delete` run `DETACH DELETE` on the node.
- `read_food` reads only non-pending images.
- `FoodItem.image_filename` stays a property, because templates build `/images/<filename>` from it. `FoodItemRepository.set_image(item_id, filename)` also replaces the item's `HAS_IMAGE` relationship, so the graph shows which dish uses which picture.
- Images are still served only through `image_response`, and SVG still only via `sanitise_svg`. The CLAUDE.md rules stay the same.
- Remove `UPLOAD_FOLDER` from `config.py`, `app/__init__.py`, `seed.py` (no more `rmtree`, because `init_db` wipes images) and `tests/conftest.py`. `MAX_CONTENT_LENGTH` stays.

## 3 Cart: `cart_repository.py` → `CartRepository` (renamed from `SessionCartRepository`)
The session holds only `customer_id` (already there) or, for a guest, a random `cart_token` (`secrets.token_hex(16)`).
- **Finding the cart:** a logged-in customer's cart is matched by `(:Customer {id})-[:HAS_CART]->(c:Cart)`. A guest's cart is matched by `(c:Cart {token})`, and only if no customer owns it. A guessed or old token can never open a customer's cart.
- **`load() -> Cart`:** one query for `HAS_ITEM` (food item id and quantity). With no cart it returns an empty `Cart`, without creating a node. It keeps ignoring quantities ≤ 0.
- **`save(cart)`:**
  - A guest gets a token on the first save, then `MERGE`s the cart. A customer `MERGE`s `(cu)-[:HAS_CART]->(c:Cart)`.
  - It replaces the `HAS_ITEM` relationships and sets `updated_at`. An empty cart is deleted (same as `clear()`).
  - It removes guest carts not touched for 30 days.
- **`clear()`:** deletes the current cart node and drops `cart_token` from the session.
- **`merge_into_customer(guest_cart)`:** after login, adds the guest's dishes to the customer's saved cart. If the same dish is in both, the guest cart's quantity wins, because it is the latest choice. Then it saves.
- **Rules kept:**
  - The cart still holds only ids and quantities. Prices still always come from `FoodItemRepository`, and the minimum-order rules stay in `Cart`.
  - Deleting a food item (`DETACH DELETE`) also removes it from carts. Unpublished items are still dropped by `cart.lines(...)` as today.
- **`auth.log_in`:** `guest = carts.load(); carts.clear(); session.clear(); session["customer_id"] = id; carts.merge_into_customer(guest)`. The session is still renewed on login.
- **`auth.log_out`:** unchanged (`session.clear()`). The customer's cart stays in Neo4j for the next login, and the browser shows an empty cart, so the next person on a shared computer still starts clean.
- Rename the class in `repositories/__init__.py`, `auth.py` and `shop.py`.

## 4 Tests
- **`test_images.py`:** `pending_files(app)` becomes `pending_images(app) -> dict[name, bytes]`, which queries `(:Image {pending: true})`. The handful of `.name`/`.suffix`/`.read_bytes()` uses are adapted. New tests:
  - a saved picture is an `Image` node linked with `HAS_IMAGE`, and the old picture node is deleted when it is replaced;
  - pending images older than one day are purged.
- **`test_cart.py`:** the existing tests stay as they are, including the one where the cart survives login and is emptied on logout. New tests:
  - logging in again (another `test_client`, i.e. another device) shows the saved cart;
  - a guest cart merges into the saved cart, and the guest quantity wins;
  - checkout empties the customer's cart;
  - a guest token cannot read a customer's cart;
  - deleting a food item removes it from carts;
  - old guest carts are purged.
- `tests/test_neo4j_repositories.py`: check the `Cart`/`Image` constraints after `init_db`.

## 5 Docs
- **CLAUDE.md**:
  - Storage bullet: Neo4j now holds data, pictures (`ImageStore`) and carts (`CartRepository`).
  - Cart rule: "The cart lives in Neo4j, `(:Cart)-[:HAS_ITEM {quantity}]->(:FoodItem)`, linked to the customer after login. The session holds only a guest cart token. Prices always come from `FoodItemRepository`…"
- **README**: describe pictures and carts in Neo4j, and remove the mentions of uploaded files on disk.
- Save this plan as `docs/plans/07-images-and-cart-in-neo4j.md`.

## Verification
1. `pytest`: the full suite passes against `neo4j-test`.
2. Run `python seed.py`. Neo4j Browser should show 9 `Image` nodes, each linked from a dish with `HAS_IMAGE`, and the menu should show the pictures.
3. Run `flask --app app run`:
   - As a guest, add dishes, log in, and see the cart kept.
   - Log out and see an empty cart.
   - Log in again, in a private window, and see the cart back.
   - As admin, upload and generate a picture, preview it, then save or discard it.
4. Run `MATCH (cu:Customer)-[:HAS_CART]->(:Cart)-[h:HAS_ITEM]->(f) RETURN cu.name, f.name_en, h.quantity` in Neo4j Browser.
5. Commit on `main` and push. This was already authorised for this branch.

## Changes during implementation
- The driver switches off "unrecognized" notifications. On a fresh database, Neo4j otherwise logs a warning about `HAS_CART` not existing yet on every page, until the first cart is saved.
- `seed.py` no longer touches `instance/uploads/`. Old folders can be deleted by hand.
