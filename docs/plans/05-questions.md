# Plan 05 – Questions about orders (C5 ask, A4 answer)

Status: agreed 2026-10-27.

## Context
These are the last two minimum requirements of Oblig 4:
- **C5 Questions:** the customer asks a question about a **specific order** and reads Ekte Mat's answer.
- **A4 Questions:** the admin reads and answers customers' questions about their orders.

**What already exists:**
- [app/models/question.py](app/models/question.py) has `Question` with `customer_id, name, email, subject, body, answer, created_at, answered_at`.
- [question_repository.py](app/models/repositories/question_repository.py) has `add` and `list_all`.
- The customer's order page `/account/orders/<id>` (C4) checks ownership, and the admin order page `/admin/orders/<id>` (A3) exists.

**What's missing:** the `question` table has **no link to an order**. Adding one is the only database change, so teammates must run `python seed.py` once after pulling.

Everything still follows CLAUDE.md: the rules are in the domain, only repositories touch storage, there are CSRF tokens and `@admin_required`/ownership checks, the text is in British English, and every feature has tests.

## 1 Domain model ([question.py](app/models/question.py))
- Add `order_id: int` (required for new questions).
- `MAX_SUBJECT = 120`, `MAX_TEXT = 2000`.
- `validate() -> list[str]`: the subject and the question are required and within their maximum lengths.
- `give_answer(text, now)`: checks the answer (required, at most 2000 characters, otherwise `ValueError`), then sets `answer` and `answered_at`. The admin can **change** an answer later; `answered_at` is then updated.
- `is_answered` (a property).
- `Question.for_order(order, customer, subject, body)` fills in the customer's name and e-mail and the order id. The controller doesn't build these fields by hand.

## 2 Repository
**[schema.sql](app/models/repositories/schema.sql):** add `order_id INTEGER NOT NULL REFERENCES customer_order (id) ON DELETE CASCADE` to `question`, plus an index on `order_id`.

**[question_repository.py](app/models/repositories/question_repository.py):**
- `add` (now with `order_id`) and `get(id)`;
- `list_by_order(order_id)`, oldest first, so a conversation reads top to bottom;
- `search(answered: Optional[bool])`: unanswered questions first and then the newest, for the admin list;
- `save_answer(question)`;
- `count_unanswered()`, for the admin dashboard;
- `count_by_order(order_ids) -> dict[int, (total, unanswered)]`, one query for the "My orders" and admin order lists.

## 3 Controllers
**C5, account blueprint ([account.py](app/controllers/account.py)):**
- `GET /account/orders/<id>` (the existing page) now also shows the order's questions with their answers, followed by an **"Ask a question about this order"** form (subject and question). It uses the same ownership check as now, so another customer's order gives 404.
- `POST /account/orders/<id>/questions` (`@login_required`, own order only):
  - it runs `Question.for_order(...)` and then `validate()`;
  - errors are shown on the same page, with the input kept and status 400;
  - on success it shows "Your question was sent. Ekte Mat will answer here." and redirects back to `#questions`.
- `GET /account/orders` gets a small "Questions" column: the number of questions and **"New answer"** when an answer exists. Unread tracking is out of scope, so the column simply shows "answered" or "waiting".

**A4, admin blueprint ([admin.py](app/controllers/admin.py)), all with `@admin_required`:**
- `GET /admin/questions?show=unanswered|all` (default **unanswered**): a list with date asked, order number (a link), customer, subject and a status label (*Waiting* or *Answered*).
- `GET /admin/questions/<id>`: the question, the customer, a link to the order with its status, the earlier questions on the same order (for context), and an **answer form**, prefilled if an answer already exists, with the button "Send answer" or "Update answer".
- `POST /admin/questions/<id>/answer`: calls `question.give_answer(text, now)`. A `ValueError` shows the form again with the error, otherwise it saves and shows "Answer sent to <customer>", then returns to the unanswered list.
- The admin order page (A3) shows that order's questions, each with an "Answer" link.
- The admin dashboard shows "Questions – N waiting for an answer".

## 4 Templates
- `account/order_detail.html`: a **Questions** section with each question and its answer (or "Waiting for an answer"), then the form.
- `account/orders.html`: the Questions column.
- `admin/questions/list.html` (new), with the filter links *Waiting* and *All*.
- `admin/questions/detail.html` (new).
- `admin/orders/detail.html`: a short list of the order's questions.
- `admin/index.html`: the dashboard line.
- `_macros.html`: `question_thread(questions)`, the shared list of questions and answers used by C5 and the admin order page.
- `base.html`: a little CSS for the question and answer boxes.

## 5 Seed ([seed.py](seed.py))
Add 3 demo questions on the demo orders:
- one **answered**, on the approved confirmation order ("Can you deliver at 17:00?" → "Yes, delivery at 17:00 is fine.");
- two **unanswered**, one on the submitted lunch order and one on the conference order.

This makes the screenshots for the report easy.

## 6 Tests
- **`test_question_model.py`**:
  - `validate()` catches each error (an empty or too long subject or question);
  - `give_answer` sets the answer and the time, refuses an empty or too long answer, and an answer can be changed;
  - `for_order` copies the customer's details.
- **`test_questions.py`** (routes):
  - C5:
    - the customer asks a question on their own order and it appears as "Waiting for an answer";
    - an error keeps the input;
    - asking on **another customer's** order gives 404, and so does a missing order;
    - visitors who aren't logged in are redirected;
    - the "My orders" column shows the count.
  - A4:
    - the pages are admin only (403 for customers);
    - the list shows only unanswered questions by default and all of them with `show=all`;
    - the detail page shows the question, a link to the order and the earlier questions;
    - an answer is saved and the **customer then sees it** on the order page;
    - an empty answer is refused;
    - an answer can be updated;
    - the dashboard count is right;
    - the admin order page lists the order's questions.
  - Repository: `list_by_order`, `search(answered=…)` and `count_by_order`.
  - One end-to-end test with **CSRF on**: the customer asks, the admin answers, the customer reads the answer.

## 7 Docs
- Save this plan to `docs/plans/05-questions.md`.
- README:
  - Features: C5 and A4;
  - a note that the seed must be run again because of the database change.
- CLAUDE.md: the rule "Questions always belong to an order; customers only see questions on their own orders."

## Verification
1. `python seed.py`, then `pytest`: all tests pass, the 128 old ones and the new ones.
2. `flask --app app run --debug`:
   - as `private.customer@example.com`: **My orders** → open an order → ask "Can we change the date?" The question shows *Waiting for an answer*;
   - as `admin@ektemat.example`: the dashboard shows "1 waiting" (plus the seeded ones) → **Questions** → open it → answer → it disappears from *Waiting*;
   - back as the customer: the answer is shown under the question.
