-- Ekte Mat Online - SQLite schema (plans 01-05).
-- Money columns are whole NOK. Dates/times are ISO 8601 text.

DROP TABLE IF EXISTS question;
DROP TABLE IF EXISTS order_line;
DROP TABLE IF EXISTS guest_group;
DROP TABLE IF EXISTS customer_order;
DROP TABLE IF EXISTS customer;
DROP TABLE IF EXISTS food_item_dietary_label;
DROP TABLE IF EXISTS food_item_allergen;
DROP TABLE IF EXISTS food_item_category;
DROP TABLE IF EXISTS food_item;

CREATE TABLE food_item (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name_en TEXT NOT NULL,
  name_no TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  price_nok INTEGER NOT NULL CHECK (price_nok >= 0),
  min_order_quantity INTEGER NOT NULL DEFAULT 1 CHECK (min_order_quantity >= 1),
  image_filename TEXT,
  published INTEGER NOT NULL DEFAULT 1 CHECK (published IN (0, 1))
);

-- Many-to-many value sets of a food item (relationships in the later Neo4j model).
CREATE TABLE food_item_category (
  food_item_id INTEGER NOT NULL REFERENCES food_item (id) ON DELETE CASCADE,
  value TEXT NOT NULL CHECK (value IN ('birthday', 'confirmation', 'wedding', 'conference', 'christmas_party', 'lunch_meeting', 'other')),
  PRIMARY KEY (food_item_id, value)
);

CREATE TABLE food_item_allergen (
  food_item_id INTEGER NOT NULL REFERENCES food_item (id) ON DELETE CASCADE,
  value TEXT NOT NULL CHECK (value IN ('gluten', 'crustaceans', 'eggs', 'fish', 'peanuts', 'soybeans', 'milk', 'nuts', 'celery', 'mustard', 'sesame', 'sulphites', 'lupin', 'molluscs')),
  PRIMARY KEY (food_item_id, value)
);

CREATE TABLE food_item_dietary_label (
  food_item_id INTEGER NOT NULL REFERENCES food_item (id) ON DELETE CASCADE,
  value TEXT NOT NULL CHECK (value IN ('vegetarian', 'vegan', 'gluten_free', 'lactose_free')),
  PRIMARY KEY (food_item_id, value)
);

CREATE TABLE customer (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  phone TEXT,
  customer_type TEXT NOT NULL CHECK (customer_type IN ('private', 'corporate')),
  organisation_number TEXT UNIQUE,
  password_hash TEXT NOT NULL DEFAULT '',
  is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
  created_at TEXT NOT NULL
);

-- "order" is a reserved word in SQL, hence customer_order.
CREATE TABLE customer_order (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_number TEXT NOT NULL UNIQUE,
  customer_id INTEGER NOT NULL REFERENCES customer (id),
  event_type TEXT NOT NULL CHECK (event_type IN ('birthday', 'confirmation', 'wedding', 'conference', 'christmas_party', 'lunch_meeting', 'other')),
  event_date TEXT NOT NULL,
  delivery_method TEXT NOT NULL CHECK (delivery_method IN ('delivery', 'pick_up')),
  delivery_address TEXT,
  status TEXT NOT NULL DEFAULT 'submitted'
    CHECK (status IN ('submitted', 'approved', 'in_preparation', 'delivered', 'rejected', 'cancelled')),
  payment_status TEXT NOT NULL DEFAULT 'not_paid'
    CHECK (payment_status IN ('not_paid', 'deposit_paid', 'invoiced', 'paid')),
  created_at TEXT NOT NULL
);

CREATE TABLE guest_group (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES customer_order (id) ON DELETE CASCADE,
  label TEXT,
  guest_count INTEGER NOT NULL CHECK (guest_count > 0),
  diet_notes TEXT
);

CREATE TABLE order_line (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES customer_order (id) ON DELETE CASCADE,
  food_item_id INTEGER NOT NULL REFERENCES food_item (id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price_nok INTEGER NOT NULL CHECK (unit_price_nok >= 0)
);

CREATE TABLE question (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES customer_order (id) ON DELETE CASCADE,
  customer_id INTEGER REFERENCES customer (id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  answer TEXT,
  created_at TEXT NOT NULL,
  answered_at TEXT
);

CREATE INDEX question_order_idx ON question (order_id);
