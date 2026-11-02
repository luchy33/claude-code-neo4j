-- Ekte Mat Online - PostgreSQL schema generated from 02_uml_domain-class_2026-10-22.puml
-- Generator: 02_uml_check-and-ddl_2026-10-22.py. Do not edit by hand: change the model and regenerate.
-- Money columns are NOK. Every mapping decision is listed in 02_sql_mapping-decisions_2026-10-22.md.

BEGIN;

CREATE TYPE order_status AS ENUM ('REQUESTED', 'REJECTED', 'AWAITING_DEPOSIT', 'CONFIRMED', 'IN_PREPARATION', 'DELIVERED', 'INVOICED', 'CANCELLED');
CREATE TYPE event_type AS ENUM ('LUNCH_MEETING', 'PARTY', 'WEDDING_DINNER', 'OTHER');
CREATE TYPE order_channel AS ENUM ('ONLINE', 'PHONE', 'EMAIL');
CREATE TYPE delivery_method AS ENUM ('DELIVERY', 'PICK_UP');
CREATE TYPE weekday AS ENUM ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN');
CREATE TYPE supplier_type AS ENUM ('FARM', 'BOAT', 'OTHER');
CREATE TYPE staff_role AS ENUM ('EVENT_COORDINATOR', 'HEAD_CHEF', 'KITCHEN_STAFF', 'OWNER');
CREATE TYPE invoice_format AS ENUM ('EHF', 'PDF');
CREATE TYPE invoice_status AS ENUM ('DRAFT', 'TRANSFERRED_TO_FIKEN');
CREATE TYPE payment_type AS ENUM ('DEPOSIT', 'FULL');
CREATE TYPE payment_status AS ENUM ('REQUESTED', 'PAID');
CREATE TYPE request_type AS ENUM ('ACCESS', 'DELETION');
CREATE TYPE customer_type AS ENUM ('PRIVATE_CUSTOMER', 'CORPORATE_CUSTOMER');

CREATE TABLE customer (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  customer_type customer_type NOT NULL,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (id, customer_type)
);

CREATE TABLE private_customer (
  customer_id BIGINT PRIMARY KEY,
  customer_type customer_type NOT NULL DEFAULT 'PRIVATE_CUSTOMER' CHECK (customer_type = 'PRIVATE_CUSTOMER'),
  FOREIGN KEY (customer_id, customer_type) REFERENCES customer (id, customer_type) ON DELETE CASCADE
);

CREATE TABLE corporate_customer (
  customer_id BIGINT PRIMARY KEY,
  customer_type customer_type NOT NULL DEFAULT 'CORPORATE_CUSTOMER' CHECK (customer_type = 'CORPORATE_CUSTOMER'),
  organisation_number TEXT NOT NULL UNIQUE,
  monthly_invoicing BOOLEAN NOT NULL,
  relationship_ended_at TIMESTAMPTZ,
  FOREIGN KEY (customer_id, customer_type) REFERENCES customer (id, customer_type) ON DELETE CASCADE
);

CREATE TABLE company_user (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  corporate_customer_id BIGINT NOT NULL,
  FOREIGN KEY (corporate_customer_id) REFERENCES corporate_customer (customer_id) ON DELETE CASCADE
);
CREATE INDEX company_user_corporate_customer_id_idx ON company_user (corporate_customer_id);

CREATE TABLE standing_order (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  weekday weekday NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE,
  active BOOLEAN NOT NULL,
  delivery_method delivery_method NOT NULL,
  delivery_address TEXT,
  delivery_time TIME,
  customer_reference TEXT,
  corporate_customer_id BIGINT NOT NULL,
  FOREIGN KEY (corporate_customer_id) REFERENCES corporate_customer (customer_id) ON DELETE RESTRICT
);
CREATE INDEX standing_order_corporate_customer_id_idx ON standing_order (corporate_customer_id);

CREATE TABLE customer_order (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_number TEXT NOT NULL UNIQUE,
  event_type event_type NOT NULL,
  event_date DATE NOT NULL,
  status order_status NOT NULL,
  channel order_channel NOT NULL,
  delivery_method delivery_method NOT NULL,
  delivery_address TEXT,
  requested_delivery_time TIME,
  customer_reference TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  reminder_sent_at TIMESTAMPTZ,
  customer_id BIGINT NOT NULL,
  company_user_id BIGINT,
  standing_order_id BIGINT,
  FOREIGN KEY (customer_id) REFERENCES customer (id) ON DELETE RESTRICT,
  FOREIGN KEY (company_user_id) REFERENCES company_user (id) ON DELETE SET NULL,
  FOREIGN KEY (standing_order_id) REFERENCES standing_order (id) ON DELETE SET NULL
);
CREATE INDEX customer_order_customer_id_idx ON customer_order (customer_id);
CREATE INDEX customer_order_company_user_id_idx ON customer_order (company_user_id);
CREATE INDEX customer_order_standing_order_id_idx ON customer_order (standing_order_id);

CREATE TABLE guest_group (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  label TEXT,
  guest_count INTEGER NOT NULL CHECK (guest_count >0),
  diet_notes TEXT,
  customer_order_id BIGINT NOT NULL,
  FOREIGN KEY (customer_order_id) REFERENCES customer_order (id) ON DELETE CASCADE
);
CREATE INDEX guest_group_customer_order_id_idx ON guest_group (customer_order_id);

CREATE TABLE dish (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name_no TEXT NOT NULL,
  name_en TEXT NOT NULL,
  price_per_person_nok NUMERIC(12,2) NOT NULL CHECK (price_per_person_nok >=0)
);

CREATE TABLE order_line (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  quantity INTEGER NOT NULL CHECK (quantity >0),
  customer_order_id BIGINT NOT NULL,
  dish_id BIGINT NOT NULL,
  FOREIGN KEY (customer_order_id) REFERENCES customer_order (id) ON DELETE CASCADE,
  FOREIGN KEY (dish_id) REFERENCES dish (id) ON DELETE RESTRICT
);
CREATE INDEX order_line_customer_order_id_idx ON order_line (customer_order_id);
CREATE INDEX order_line_dish_id_idx ON order_line (dish_id);

CREATE TABLE menu (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season TEXT NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE,
  published BOOLEAN NOT NULL
);

CREATE TABLE allergen (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name_no TEXT NOT NULL,
  name_en TEXT NOT NULL
);

CREATE TABLE supplier (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL,
  supplier_type supplier_type NOT NULL,
  location TEXT
);

CREATE TABLE ingredient (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL,
  supplier_id BIGINT,
  FOREIGN KEY (supplier_id) REFERENCES supplier (id) ON DELETE SET NULL
);
CREATE INDEX ingredient_supplier_id_idx ON ingredient (supplier_id);

CREATE TABLE staff_user (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL,
  role staff_role NOT NULL,
  pin_hash TEXT
);

CREATE TABLE allergy_confirmation (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  confirmed_at TIMESTAMPTZ NOT NULL,
  customer_order_id BIGINT NOT NULL UNIQUE,
  staff_user_id BIGINT NOT NULL,
  FOREIGN KEY (customer_order_id) REFERENCES customer_order (id) ON DELETE CASCADE,
  FOREIGN KEY (staff_user_id) REFERENCES staff_user (id) ON DELETE RESTRICT
);
CREATE INDEX allergy_confirmation_staff_user_id_idx ON allergy_confirmation (staff_user_id);

CREATE TABLE standing_order_line (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  quantity INTEGER NOT NULL CHECK (quantity >0),
  standing_order_id BIGINT NOT NULL,
  dish_id BIGINT NOT NULL,
  FOREIGN KEY (standing_order_id) REFERENCES standing_order (id) ON DELETE CASCADE,
  FOREIGN KEY (dish_id) REFERENCES dish (id) ON DELETE RESTRICT
);
CREATE INDEX standing_order_line_standing_order_id_idx ON standing_order_line (standing_order_id);
CREATE INDEX standing_order_line_dish_id_idx ON standing_order_line (dish_id);

CREATE TABLE invoice (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  invoice_number TEXT NOT NULL UNIQUE,
  period_start DATE,
  period_end DATE,
  format invoice_format NOT NULL,
  status invoice_status NOT NULL,
  fiken_invoice_id TEXT UNIQUE,
  issued_at TIMESTAMPTZ,
  customer_id BIGINT NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customer (id) ON DELETE RESTRICT
);
CREATE INDEX invoice_customer_id_idx ON invoice (customer_id);

CREATE TABLE invoice_line (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  description TEXT NOT NULL,
  amount_nok NUMERIC(12,2) NOT NULL CHECK (amount_nok >=0),
  customer_reference TEXT,
  invoice_id BIGINT NOT NULL,
  customer_order_id BIGINT NOT NULL UNIQUE,
  FOREIGN KEY (invoice_id) REFERENCES invoice (id) ON DELETE CASCADE,
  FOREIGN KEY (customer_order_id) REFERENCES customer_order (id) ON DELETE RESTRICT
);
CREATE INDEX invoice_line_invoice_id_idx ON invoice_line (invoice_id);

CREATE TABLE payment (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  payment_type payment_type NOT NULL,
  amount_nok NUMERIC(12,2) NOT NULL CHECK (amount_nok >0),
  vipps_reference TEXT NOT NULL UNIQUE,
  status payment_status NOT NULL,
  paid_at TIMESTAMPTZ,
  customer_order_id BIGINT NOT NULL,
  FOREIGN KEY (customer_order_id) REFERENCES customer_order (id) ON DELETE RESTRICT
);
CREATE INDEX payment_customer_order_id_idx ON payment (customer_order_id);

CREATE TABLE data_subject_request (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  request_type request_type NOT NULL,
  received_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  customer_id BIGINT NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customer (id) ON DELETE RESTRICT
);
CREATE INDEX data_subject_request_customer_id_idx ON data_subject_request (customer_id);

CREATE TABLE capacity_limit (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  valid_from DATE NOT NULL UNIQUE,
  max_covers_per_day INTEGER NOT NULL CHECK (max_covers_per_day >0),
  max_covers_with_wedding_dinner INTEGER NOT NULL CHECK (max_covers_with_wedding_dinner >0)
);

CREATE TABLE guest_group_allergen (
  guest_group_id BIGINT NOT NULL,
  allergen_id BIGINT NOT NULL,
  PRIMARY KEY (guest_group_id, allergen_id),
  FOREIGN KEY (guest_group_id) REFERENCES guest_group (id) ON DELETE CASCADE,
  FOREIGN KEY (allergen_id) REFERENCES allergen (id) ON DELETE RESTRICT
);
CREATE INDEX guest_group_allergen_allergen_id_idx ON guest_group_allergen (allergen_id);

CREATE TABLE menu_dish (
  menu_id BIGINT NOT NULL,
  dish_id BIGINT NOT NULL,
  PRIMARY KEY (menu_id, dish_id),
  FOREIGN KEY (menu_id) REFERENCES menu (id) ON DELETE CASCADE,
  FOREIGN KEY (dish_id) REFERENCES dish (id) ON DELETE RESTRICT
);
CREATE INDEX menu_dish_dish_id_idx ON menu_dish (dish_id);

CREATE TABLE dish_allergen (
  dish_id BIGINT NOT NULL,
  allergen_id BIGINT NOT NULL,
  PRIMARY KEY (dish_id, allergen_id),
  FOREIGN KEY (dish_id) REFERENCES dish (id) ON DELETE CASCADE,
  FOREIGN KEY (allergen_id) REFERENCES allergen (id) ON DELETE RESTRICT
);
CREATE INDEX dish_allergen_allergen_id_idx ON dish_allergen (allergen_id);

CREATE TABLE dish_ingredient (
  dish_id BIGINT NOT NULL,
  ingredient_id BIGINT NOT NULL,
  PRIMARY KEY (dish_id, ingredient_id),
  FOREIGN KEY (dish_id) REFERENCES dish (id) ON DELETE CASCADE,
  FOREIGN KEY (ingredient_id) REFERENCES ingredient (id) ON DELETE RESTRICT
);
CREATE INDEX dish_ingredient_ingredient_id_idx ON dish_ingredient (ingredient_id);

-- Multiplicity lower bound: CorporateCustomer must have at least 1 CompanyUser
CREATE FUNCTION chk_min_company_user_corporate_customer_id() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pid BIGINT;
BEGIN
  IF TG_TABLE_NAME = 'corporate_customer' THEN pid := NEW.customer_id; ELSE pid := OLD.corporate_customer_id; END IF;
  IF EXISTS (SELECT 1 FROM corporate_customer WHERE customer_id = pid)
     AND NOT EXISTS (SELECT 1 FROM company_user WHERE corporate_customer_id = pid) THEN
    RAISE EXCEPTION 'Multiplicity violated: CorporateCustomer must have at least 1 CompanyUser (id %)', pid;
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER chk_min_company_user_corporate_customer_id_p AFTER INSERT ON corporate_customer DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_company_user_corporate_customer_id();
CREATE CONSTRAINT TRIGGER chk_min_company_user_corporate_customer_id_c AFTER DELETE OR UPDATE OF corporate_customer_id ON company_user DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_company_user_corporate_customer_id();

-- Multiplicity lower bound: Order must have at least 1 GuestGroup
CREATE FUNCTION chk_min_guest_group_customer_order_id() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pid BIGINT;
BEGIN
  IF TG_TABLE_NAME = 'customer_order' THEN pid := NEW.id; ELSE pid := OLD.customer_order_id; END IF;
  IF EXISTS (SELECT 1 FROM customer_order WHERE id = pid)
     AND NOT EXISTS (SELECT 1 FROM guest_group WHERE customer_order_id = pid) THEN
    RAISE EXCEPTION 'Multiplicity violated: Order must have at least 1 GuestGroup (id %)', pid;
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER chk_min_guest_group_customer_order_id_p AFTER INSERT ON customer_order DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_guest_group_customer_order_id();
CREATE CONSTRAINT TRIGGER chk_min_guest_group_customer_order_id_c AFTER DELETE OR UPDATE OF customer_order_id ON guest_group DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_guest_group_customer_order_id();

-- Multiplicity lower bound: Order must have at least 1 OrderLine
CREATE FUNCTION chk_min_order_line_customer_order_id() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pid BIGINT;
BEGIN
  IF TG_TABLE_NAME = 'customer_order' THEN pid := NEW.id; ELSE pid := OLD.customer_order_id; END IF;
  IF EXISTS (SELECT 1 FROM customer_order WHERE id = pid)
     AND NOT EXISTS (SELECT 1 FROM order_line WHERE customer_order_id = pid) THEN
    RAISE EXCEPTION 'Multiplicity violated: Order must have at least 1 OrderLine (id %)', pid;
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER chk_min_order_line_customer_order_id_p AFTER INSERT ON customer_order DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_order_line_customer_order_id();
CREATE CONSTRAINT TRIGGER chk_min_order_line_customer_order_id_c AFTER DELETE OR UPDATE OF customer_order_id ON order_line DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_order_line_customer_order_id();

-- Multiplicity lower bound: Menu must have at least 1 Dish
CREATE FUNCTION chk_min_menu_dish_menu_id() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pid BIGINT;
BEGIN
  IF TG_TABLE_NAME = 'menu' THEN pid := NEW.id; ELSE pid := OLD.menu_id; END IF;
  IF EXISTS (SELECT 1 FROM menu WHERE id = pid)
     AND NOT EXISTS (SELECT 1 FROM menu_dish WHERE menu_id = pid) THEN
    RAISE EXCEPTION 'Multiplicity violated: Menu must have at least 1 Dish (id %)', pid;
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER chk_min_menu_dish_menu_id_p AFTER INSERT ON menu DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_menu_dish_menu_id();
CREATE CONSTRAINT TRIGGER chk_min_menu_dish_menu_id_c AFTER DELETE OR UPDATE OF menu_id ON menu_dish DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_menu_dish_menu_id();

-- Multiplicity lower bound: StandingOrder must have at least 1 StandingOrderLine
CREATE FUNCTION chk_min_standing_order_line_standing_order_id() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pid BIGINT;
BEGIN
  IF TG_TABLE_NAME = 'standing_order' THEN pid := NEW.id; ELSE pid := OLD.standing_order_id; END IF;
  IF EXISTS (SELECT 1 FROM standing_order WHERE id = pid)
     AND NOT EXISTS (SELECT 1 FROM standing_order_line WHERE standing_order_id = pid) THEN
    RAISE EXCEPTION 'Multiplicity violated: StandingOrder must have at least 1 StandingOrderLine (id %)', pid;
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER chk_min_standing_order_line_standing_order_id_p AFTER INSERT ON standing_order DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_standing_order_line_standing_order_id();
CREATE CONSTRAINT TRIGGER chk_min_standing_order_line_standing_order_id_c AFTER DELETE OR UPDATE OF standing_order_id ON standing_order_line DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_standing_order_line_standing_order_id();

-- Multiplicity lower bound: Invoice must have at least 1 InvoiceLine
CREATE FUNCTION chk_min_invoice_line_invoice_id() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pid BIGINT;
BEGIN
  IF TG_TABLE_NAME = 'invoice' THEN pid := NEW.id; ELSE pid := OLD.invoice_id; END IF;
  IF EXISTS (SELECT 1 FROM invoice WHERE id = pid)
     AND NOT EXISTS (SELECT 1 FROM invoice_line WHERE invoice_id = pid) THEN
    RAISE EXCEPTION 'Multiplicity violated: Invoice must have at least 1 InvoiceLine (id %)', pid;
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER chk_min_invoice_line_invoice_id_p AFTER INSERT ON invoice DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_invoice_line_invoice_id();
CREATE CONSTRAINT TRIGGER chk_min_invoice_line_invoice_id_c AFTER DELETE OR UPDATE OF invoice_id ON invoice_line DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_min_invoice_line_invoice_id();

-- Abstract class Customer: each row must have its subtype row
CREATE FUNCTION chk_customer_has_subtype() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  CASE NEW.customer_type
    WHEN 'PRIVATE_CUSTOMER' THEN PERFORM 1 FROM private_customer WHERE customer_id = NEW.id;
    WHEN 'CORPORATE_CUSTOMER' THEN PERFORM 1 FROM corporate_customer WHERE customer_id = NEW.id;
  END CASE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Abstract class Customer: id % has no subtype row', NEW.id; END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER chk_customer_has_subtype_t AFTER INSERT ON customer DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chk_customer_has_subtype();

COMMIT;
