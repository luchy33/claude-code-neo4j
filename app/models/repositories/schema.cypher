// Ekte Mat Online - Neo4j schema (plan 06). Statements are separated by semicolons.
// Record nodes get an integer `id` from a (:Counter) node, so URLs and carts keep int ids.
// Images are keyed by `name` and carts by a random `token` instead.
// Money properties are whole NOK. Dates are native `date`, timestamps native `localdatetime`.

CREATE CONSTRAINT food_item_id IF NOT EXISTS FOR (n:FoodItem) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (n:Customer) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT customer_email IF NOT EXISTS FOR (n:Customer) REQUIRE n.email IS UNIQUE;
CREATE CONSTRAINT customer_organisation_number IF NOT EXISTS FOR (n:Customer) REQUIRE n.organisation_number IS UNIQUE;
CREATE CONSTRAINT order_id IF NOT EXISTS FOR (n:Order) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT order_number IF NOT EXISTS FOR (n:Order) REQUIRE n.order_number IS UNIQUE;
CREATE CONSTRAINT guest_group_id IF NOT EXISTS FOR (n:GuestGroup) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT order_line_id IF NOT EXISTS FOR (n:OrderLine) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT question_id IF NOT EXISTS FOR (n:Question) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT image_name IF NOT EXISTS FOR (n:Image) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT cart_token IF NOT EXISTS FOR (n:Cart) REQUIRE n.token IS UNIQUE;
CREATE CONSTRAINT counter_name IF NOT EXISTS FOR (n:Counter) REQUIRE n.name IS UNIQUE;

// Fixed value nodes, shared by food items and orders (the many-to-many tables in the old SQLite schema).
// init_db() creates one node per enum value.
CREATE CONSTRAINT event_category_value IF NOT EXISTS FOR (n:EventCategory) REQUIRE n.value IS UNIQUE;
CREATE CONSTRAINT allergen_value IF NOT EXISTS FOR (n:Allergen) REQUIRE n.value IS UNIQUE;
CREATE CONSTRAINT dietary_label_value IF NOT EXISTS FOR (n:DietaryLabel) REQUIRE n.value IS UNIQUE;
