# Plan 03 – Shopping cart (C2)

Status: agreed 2026-10-27.

## Context
The Oblig 4 requirement for **C2 Shopping cart:** add, change and remove items, with an estimated total cost. **Quantities below an item's minimum order are not accepted.**

**C1 (menu by event) is already done.** Plan 02 built the cards grouped by event, showing the picture, price, minimum order and allergens, in [app/templates/shop/index.html](app/templates/shop/index.html). This plan does not change the menu layout. It only adds an "Add to cart" form to each existing card.

Decisions:
- **Quantity means portions per dish.** Prices are stored per portion, and A1 gives each dish its own minimum order. The number of guests belongs to C3 (checkout).
- **Logging in is not needed to use the cart.** C3 says "log in (or register) and submit", so the cart must **survive logging in**.

Everything still follows CLAUDE.md: only repository classes touch storage, the rules are in the domain model, every POST form has a CSRF token, prices are in NOK, the text is in British English, and every feature has tests.

## 1 Domain model: `app/models/cart.py` (new)
These are plain classes with no Flask or storage code.
- `CartLine(food_item: FoodItem, quantity: int)` with a `line_total_nok` property.
- `Cart` holds `quantities: dict[int, int]`, mapping a food item id to its number of portions.
  - `MAX_QUANTITY = 1000` per line.
  - `validate_quantity(item, quantity) -> str | None` returns an error message if the quantity is below `item.min_order_quantity`, above the maximum, or the item is unpublished. Otherwise it returns `None`.
  - `add(item, quantity)`: if the dish is already in the cart, the quantities are **added together** and the sum is checked. On an error it raises `CartError` and the cart is left unchanged.
  - `set_quantity(item, quantity)` is checked in the same way. A quantity of 0 means "remove".
  - `remove(item_id)`.
  - `lines(items_by_id) -> (list[CartLine], removed_names)`: builds the lines from the **current** food items. Prices always come from the database and are never stored in the cart. Lines for dishes that have been deleted or unpublished are dropped, and their names are returned so the customer can be told.
  - `total_nok(lines)`, `item_count`, `is_empty`.
- Add `CartError` to [app/models/errors.py](app/models/errors.py). Its message can be shown to the customer.

## 2 Storage: `app/models/repositories/cart_repository.py` (new)
- `SessionCartRepository` is the **only** code that reads or writes the cart.
  - `load() -> Cart` reads `session["cart"]` (`{"<item_id>": qty}`) and ignores broken entries.
  - `save(cart)` and `clear()`.
- It stores ids and numbers only, so it stays small enough for the cookie.
- A database or Neo4j cart could replace this class later without changing the controllers.
- Add `FoodItemRepository.get_many(ids) -> dict[int, FoodItem]`, a single query for the cart lines.

## 3 Controllers
**[shop.py](app/controllers/shop.py)**: `GET /` stays as it is. The new routes are:
- `POST /cart/add`: takes `food_item_id` and `quantity`. If the item is missing or unpublished, the result is 404. Otherwise it runs `cart.add`, saves, and shows "Added 12 × Fish soup to your cart". A `CartError` shows the message in red instead. Afterwards it redirects back to the menu, to the card's anchor (`/#item-<id>`).
- `GET /cart`: shows the lines, an editable quantity per line, a **Remove** button, the minimum per line, the **estimated total** and a "dropped items" notice.
  - The "Continue to order" button goes to the login page, with `next=/cart`, for visitors who aren't logged in. For logged-in customers it shows "Ordering comes in the next version" until C3 is built.
- `POST /cart/update`: one form holds all the quantities (`qty-<id>`). Every line is checked first, and if **any** line is invalid, nothing is saved and every error is shown. A quantity of 0 removes the line.
- `POST /cart/remove/<id>`.

**[auth.py](app/controllers/auth.py)**
- `log_in()` still calls `session.clear()`, which prevents session fixation, but now **carries the cart over**: it reads the cart before clearing and writes it back after, through `SessionCartRepository`.
- `log_out()` empties the cart as well, so the next person on a shared computer starts clean.
- A context processor adds `cart_count` to every page.

## 4 Templates
- `base.html`: a **Cart (n)** link in the navigation, plus CSS for the quantity field and the cart table.
- `shop/index.html`: the cards stay as they are, with `id="item-<id>"` added. Each card gets a small add-to-cart form: a quantity field that starts at the minimum (`min=` set to the minimum, `max=1000`), the hint "Minimum N portions", and an **Add to cart** button.
- `shop/cart.html` (new): a table of dish, price per portion, minimum, quantity input, line total and Remove, then the **estimated total**, then the "Continue to order" button. An empty cart shows a link back to the menu.
- **No JavaScript is needed.** The browser checks `min` and `max`, and the server checks the rules again.

## 5 Tests (`tests/`)
- **`test_cart_model.py`** (domain):
  - adding at or above the minimum works, and below it raises `CartError` with the minimum in the message;
  - adding the same dish twice adds the quantities;
  - `set_quantity` below the minimum is rejected, 0 removes, and above the maximum is rejected;
  - an unpublished dish is rejected;
  - the totals are right;
  - `lines()` drops dishes that are missing or unpublished and reports their names.
- **`test_cart.py`** (routes):
  - a card has the add-to-cart form, with the minimum as the starting value;
  - adding redirects to the menu and the cart count updates;
  - adding below the minimum shows the error and leaves the cart empty;
  - adding a hidden or unknown dish gives 404;
  - the cart page shows the lines and the correct total;
  - an update with one bad line saves nothing and shows the error, while a valid update saves;
  - remove works, and quantity 0 also removes;
  - a dish unpublished while in the cart disappears from it, with a notice;
  - **the cart survives logging in** and is emptied on log out;
  - one end-to-end test with CSRF switched on.

## 6 Docs
- Save this plan to `docs/plans/03-menu-and-cart.md`. This is the file name the user asked for.
- README: update the Shop line under Features.
- CLAUDE.md: add `cart_repository` to the description of the storage layer, and the rule "The cart lives in the session and holds only item ids and quantities; prices always come from `FoodItemRepository`."

## Verification
1. `pytest`: all tests pass, the 58 old ones and the new ones.
2. `flask --app app run --debug`, then in the browser:
   - add 5 × Three-course wedding dinner, which has a minimum of 30. It is **refused** with a message;
   - add 30, and **Cart (1)** appears;
   - in the cart, change the quantity to 40, and the total updates to 40 × 695 = 27 800 NOK;
   - set it to 10, which is **refused**, and nothing changes;
   - remove it;
   - add something, then log in. The cart is still there.
