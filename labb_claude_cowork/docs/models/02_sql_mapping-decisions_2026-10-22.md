# SQL DDL mapping decisions (2026-10-22)

Model-driven step: `02_sql_ekte-mat-schema_postgresql_2026-10-22.sql` is generated from `02_uml_domain-class_2026-10-22.puml` by `02_uml_check-and-ddl_2026-10-22.py`. Each row below is logged by the generator when it applies a rule.

## General rules

1. **Class -> table.** Names become snake_case. `Order` becomes `customer_order` because ORDER is a reserved SQL word.
2. **Identity.** Each table gets a surrogate key `id BIGINT GENERATED ALWAYS AS IDENTITY`. Business keys marked `{unique}` (orderNumber, invoiceNumber, ...) become UNIQUE columns.
3. **Attribute multiplicity.** `[1]` becomes NOT NULL; `[0..1]` becomes a nullable column.
4. **Types.** String -> TEXT, Integer -> INTEGER, Boolean -> BOOLEAN, Date -> DATE, DateTime -> TIMESTAMPTZ (time zone safe), Time -> TIME, Money -> NUMERIC(12,2) in NOK (exact; never FLOAT for money).
5. **Enumerations** become PostgreSQL ENUM types, so only the modelled values can be stored.
6. **Constraints.** `{>0}` and `{>=0}` become CHECK constraints.
7. **Association with upper bound 1 on one end (1 or 0..1 to many).** The FK goes in the table on the many end. A lower bound of 1 on the one end gives NOT NULL; 0 gives a nullable FK.
8. **One-to-one (1 to 0..1).** The FK goes in the optional side and gets UNIQUE, so the mandatory side can have at most one partner.
9. **Many-to-many** becomes a junction table with a composite primary key, which also prevents duplicate links.
10. **Delete behaviour:**
    - Composition (filled diamond) -> ON DELETE CASCADE, because the parts cannot exist without the whole.
    - Optional link -> SET NULL.
    - Mandatory reference -> RESTRICT, so data still in use cannot be removed.
    - Junction tables: CASCADE from the owning (left) class and RESTRICT from the referenced class, e.g. an allergen still labelling a dish cannot be deleted.
11. **Lower bound 1 on a many end (1..\*)** cannot be expressed with foreign keys. It is enforced by a DEFERRABLE INITIALLY DEFERRED constraint trigger, checked at COMMIT so the parent and its first child can be inserted in the same transaction.
12. **Generalisation** uses class-table inheritance:
    - The parent table holds the shared attributes plus a discriminator (`customer_type`).
    - Each subclass table uses the parent's id as its primary key and foreign key.
    - A composite FK (id, type) ensures a subtype row matches the parent's type.
    - The abstract parent gets a deferred trigger so every customer has its subtype row.
    - Chosen over single-table inheritance (many nullable subtype columns) and concrete-table inheritance (Order could not reference one customer table).
13. **Indexes.** PostgreSQL does not index FK columns automatically, so each FK gets an index (except where UNIQUE or the PK already provides one).

## Decision log (every element)

| # | Model element | Mapping rule applied | SQL result |
|---|---|---|---|
| 1 | class Order | Reserved SQL word avoided | table customer_order |
| 2 | enum OrderStatus | Enumeration -> PostgreSQL ENUM type | TYPE order_status |
| 3 | enum EventType | Enumeration -> PostgreSQL ENUM type | TYPE event_type |
| 4 | enum OrderChannel | Enumeration -> PostgreSQL ENUM type | TYPE order_channel |
| 5 | enum DeliveryMethod | Enumeration -> PostgreSQL ENUM type | TYPE delivery_method |
| 6 | enum Weekday | Enumeration -> PostgreSQL ENUM type | TYPE weekday |
| 7 | enum SupplierType | Enumeration -> PostgreSQL ENUM type | TYPE supplier_type |
| 8 | enum StaffRole | Enumeration -> PostgreSQL ENUM type | TYPE staff_role |
| 9 | enum InvoiceFormat | Enumeration -> PostgreSQL ENUM type | TYPE invoice_format |
| 10 | enum InvoiceStatus | Enumeration -> PostgreSQL ENUM type | TYPE invoice_status |
| 11 | enum PaymentType | Enumeration -> PostgreSQL ENUM type | TYPE payment_type |
| 12 | enum PaymentStatus | Enumeration -> PostgreSQL ENUM type | TYPE payment_status |
| 13 | enum RequestType | Enumeration -> PostgreSQL ENUM type | TYPE request_type |
| 14 | abstract Customer | Discriminator type for subclasses | TYPE customer_type |
| 15 | class Customer | Class -> table with surrogate key | customer.id IDENTITY PK |
| 16 | Customer.name : String [1] | [1] -> NOT NULL; String -> TEXT | customer.name TEXT NOT NULL |
| 17 | Customer.email : String [0..1] | [0..1] -> nullable; String -> TEXT | customer.email TEXT |
| 18 | Customer.phone : String [0..1] | [0..1] -> nullable; String -> TEXT | customer.phone TEXT |
| 19 | Customer.createdAt : DateTime [1] | [1] -> NOT NULL; DateTime -> TIMESTAMPTZ | customer.created_at TIMESTAMPTZ NOT NULL |
| 20 | Customer <\|-- PrivateCustomer | Generalisation -> class-table inheritance: subclass table shares the parent key; composite FK (id, type) makes a row valid only for the matching subtype | private_customer.customer_id PK/FK -> customer.id |
| 21 | Customer <\|-- CorporateCustomer | Generalisation -> class-table inheritance: subclass table shares the parent key; composite FK (id, type) makes a row valid only for the matching subtype | corporate_customer.customer_id PK/FK -> customer.id |
| 22 | CorporateCustomer.organisationNumber : String [1] {unique} | [1] -> NOT NULL; String -> TEXT; {unique} -> UNIQUE | corporate_customer.organisation_number TEXT NOT NULL UNIQUE |
| 23 | CorporateCustomer.monthlyInvoicing : Boolean [1] | [1] -> NOT NULL; Boolean -> BOOLEAN | corporate_customer.monthly_invoicing BOOLEAN NOT NULL |
| 24 | CorporateCustomer.relationshipEndedAt : DateTime [0..1] | [0..1] -> nullable; DateTime -> TIMESTAMPTZ | corporate_customer.relationship_ended_at TIMESTAMPTZ |
| 25 | class CompanyUser | Class -> table with surrogate key | company_user.id IDENTITY PK |
| 26 | CompanyUser.name : String [1] | [1] -> NOT NULL; String -> TEXT | company_user.name TEXT NOT NULL |
| 27 | CompanyUser.email : String [1] {unique} | [1] -> NOT NULL; String -> TEXT; {unique} -> UNIQUE | company_user.email TEXT NOT NULL UNIQUE |
| 28 | class Order | Class -> table with surrogate key | customer_order.id IDENTITY PK |
| 29 | Order.orderNumber : String [1] {unique} | [1] -> NOT NULL; String -> TEXT; {unique} -> UNIQUE | customer_order.order_number TEXT NOT NULL UNIQUE |
| 30 | Order.eventType : EventType [1] | [1] -> NOT NULL; EventType -> event_type | customer_order.event_type event_type NOT NULL |
| 31 | Order.eventDate : Date [1] | [1] -> NOT NULL; Date -> DATE | customer_order.event_date DATE NOT NULL |
| 32 | Order.status : OrderStatus [1] | [1] -> NOT NULL; OrderStatus -> order_status | customer_order.status order_status NOT NULL |
| 33 | Order.channel : OrderChannel [1] | [1] -> NOT NULL; OrderChannel -> order_channel | customer_order.channel order_channel NOT NULL |
| 34 | Order.deliveryMethod : DeliveryMethod [1] | [1] -> NOT NULL; DeliveryMethod -> delivery_method | customer_order.delivery_method delivery_method NOT NULL |
| 35 | Order.deliveryAddress : String [0..1] | [0..1] -> nullable; String -> TEXT | customer_order.delivery_address TEXT |
| 36 | Order.requestedDeliveryTime : Time [0..1] | [0..1] -> nullable; Time -> TIME | customer_order.requested_delivery_time TIME |
| 37 | Order.customerReference : String [0..1] | [0..1] -> nullable; String -> TEXT | customer_order.customer_reference TEXT |
| 38 | Order.createdAt : DateTime [1] | [1] -> NOT NULL; DateTime -> TIMESTAMPTZ | customer_order.created_at TIMESTAMPTZ NOT NULL |
| 39 | Order.reminderSentAt : DateTime [0..1] | [0..1] -> nullable; DateTime -> TIMESTAMPTZ | customer_order.reminder_sent_at TIMESTAMPTZ |
| 40 | class GuestGroup | Class -> table with surrogate key | guest_group.id IDENTITY PK |
| 41 | GuestGroup.label : String [0..1] | [0..1] -> nullable; String -> TEXT | guest_group.label TEXT |
| 42 | GuestGroup.guestCount : Integer [1] {>0} | [1] -> NOT NULL; Integer -> INTEGER; {>0} -> CHECK | guest_group.guest_count INTEGER NOT NULL CHECK (guest_count >0) |
| 43 | GuestGroup.dietNotes : String [0..1] | [0..1] -> nullable; String -> TEXT | guest_group.diet_notes TEXT |
| 44 | class OrderLine | Class -> table with surrogate key | order_line.id IDENTITY PK |
| 45 | OrderLine.quantity : Integer [1] {>0} | [1] -> NOT NULL; Integer -> INTEGER; {>0} -> CHECK | order_line.quantity INTEGER NOT NULL CHECK (quantity >0) |
| 46 | class Menu | Class -> table with surrogate key | menu.id IDENTITY PK |
| 47 | Menu.season : String [1] | [1] -> NOT NULL; String -> TEXT | menu.season TEXT NOT NULL |
| 48 | Menu.validFrom : Date [1] | [1] -> NOT NULL; Date -> DATE | menu.valid_from DATE NOT NULL |
| 49 | Menu.validTo : Date [0..1] | [0..1] -> nullable; Date -> DATE | menu.valid_to DATE |
| 50 | Menu.published : Boolean [1] | [1] -> NOT NULL; Boolean -> BOOLEAN | menu.published BOOLEAN NOT NULL |
| 51 | class Dish | Class -> table with surrogate key | dish.id IDENTITY PK |
| 52 | Dish.nameNo : String [1] | [1] -> NOT NULL; String -> TEXT | dish.name_no TEXT NOT NULL |
| 53 | Dish.nameEn : String [1] | [1] -> NOT NULL; String -> TEXT | dish.name_en TEXT NOT NULL |
| 54 | Dish.pricePerPersonNok : Money [1] {>=0} | [1] -> NOT NULL; Money -> NUMERIC(12,2); {>=0} -> CHECK | dish.price_per_person_nok NUMERIC(12,2) NOT NULL CHECK (price_per_person_nok >=0) |
| 55 | class Allergen | Class -> table with surrogate key | allergen.id IDENTITY PK |
| 56 | Allergen.code : String [1] {unique} | [1] -> NOT NULL; String -> TEXT; {unique} -> UNIQUE | allergen.code TEXT NOT NULL UNIQUE |
| 57 | Allergen.nameNo : String [1] | [1] -> NOT NULL; String -> TEXT | allergen.name_no TEXT NOT NULL |
| 58 | Allergen.nameEn : String [1] | [1] -> NOT NULL; String -> TEXT | allergen.name_en TEXT NOT NULL |
| 59 | class Ingredient | Class -> table with surrogate key | ingredient.id IDENTITY PK |
| 60 | Ingredient.name : String [1] | [1] -> NOT NULL; String -> TEXT | ingredient.name TEXT NOT NULL |
| 61 | class Supplier | Class -> table with surrogate key | supplier.id IDENTITY PK |
| 62 | Supplier.name : String [1] | [1] -> NOT NULL; String -> TEXT | supplier.name TEXT NOT NULL |
| 63 | Supplier.supplierType : SupplierType [1] | [1] -> NOT NULL; SupplierType -> supplier_type | supplier.supplier_type supplier_type NOT NULL |
| 64 | Supplier.location : String [0..1] | [0..1] -> nullable; String -> TEXT | supplier.location TEXT |
| 65 | class StaffUser | Class -> table with surrogate key | staff_user.id IDENTITY PK |
| 66 | StaffUser.name : String [1] | [1] -> NOT NULL; String -> TEXT | staff_user.name TEXT NOT NULL |
| 67 | StaffUser.role : StaffRole [1] | [1] -> NOT NULL; StaffRole -> staff_role | staff_user.role staff_role NOT NULL |
| 68 | StaffUser.pinHash : String [0..1] | [0..1] -> nullable; String -> TEXT | staff_user.pin_hash TEXT |
| 69 | class AllergyConfirmation | Class -> table with surrogate key | allergy_confirmation.id IDENTITY PK |
| 70 | AllergyConfirmation.confirmedAt : DateTime [1] | [1] -> NOT NULL; DateTime -> TIMESTAMPTZ | allergy_confirmation.confirmed_at TIMESTAMPTZ NOT NULL |
| 71 | class StandingOrder | Class -> table with surrogate key | standing_order.id IDENTITY PK |
| 72 | StandingOrder.weekday : Weekday [1] | [1] -> NOT NULL; Weekday -> weekday | standing_order.weekday weekday NOT NULL |
| 73 | StandingOrder.startDate : Date [1] | [1] -> NOT NULL; Date -> DATE | standing_order.start_date DATE NOT NULL |
| 74 | StandingOrder.endDate : Date [0..1] | [0..1] -> nullable; Date -> DATE | standing_order.end_date DATE |
| 75 | StandingOrder.active : Boolean [1] | [1] -> NOT NULL; Boolean -> BOOLEAN | standing_order.active BOOLEAN NOT NULL |
| 76 | StandingOrder.deliveryMethod : DeliveryMethod [1] | [1] -> NOT NULL; DeliveryMethod -> delivery_method | standing_order.delivery_method delivery_method NOT NULL |
| 77 | StandingOrder.deliveryAddress : String [0..1] | [0..1] -> nullable; String -> TEXT | standing_order.delivery_address TEXT |
| 78 | StandingOrder.deliveryTime : Time [0..1] | [0..1] -> nullable; Time -> TIME | standing_order.delivery_time TIME |
| 79 | StandingOrder.customerReference : String [0..1] | [0..1] -> nullable; String -> TEXT | standing_order.customer_reference TEXT |
| 80 | class StandingOrderLine | Class -> table with surrogate key | standing_order_line.id IDENTITY PK |
| 81 | StandingOrderLine.quantity : Integer [1] {>0} | [1] -> NOT NULL; Integer -> INTEGER; {>0} -> CHECK | standing_order_line.quantity INTEGER NOT NULL CHECK (quantity >0) |
| 82 | class Invoice | Class -> table with surrogate key | invoice.id IDENTITY PK |
| 83 | Invoice.invoiceNumber : String [1] {unique} | [1] -> NOT NULL; String -> TEXT; {unique} -> UNIQUE | invoice.invoice_number TEXT NOT NULL UNIQUE |
| 84 | Invoice.periodStart : Date [0..1] | [0..1] -> nullable; Date -> DATE | invoice.period_start DATE |
| 85 | Invoice.periodEnd : Date [0..1] | [0..1] -> nullable; Date -> DATE | invoice.period_end DATE |
| 86 | Invoice.format : InvoiceFormat [1] | [1] -> NOT NULL; InvoiceFormat -> invoice_format | invoice.format invoice_format NOT NULL |
| 87 | Invoice.status : InvoiceStatus [1] | [1] -> NOT NULL; InvoiceStatus -> invoice_status | invoice.status invoice_status NOT NULL |
| 88 | Invoice.fikenInvoiceId : String [0..1] {unique} | [0..1] -> nullable; String -> TEXT; {unique} -> UNIQUE | invoice.fiken_invoice_id TEXT UNIQUE |
| 89 | Invoice.issuedAt : DateTime [0..1] | [0..1] -> nullable; DateTime -> TIMESTAMPTZ | invoice.issued_at TIMESTAMPTZ |
| 90 | class InvoiceLine | Class -> table with surrogate key | invoice_line.id IDENTITY PK |
| 91 | InvoiceLine.description : String [1] | [1] -> NOT NULL; String -> TEXT | invoice_line.description TEXT NOT NULL |
| 92 | InvoiceLine.amountNok : Money [1] {>=0} | [1] -> NOT NULL; Money -> NUMERIC(12,2); {>=0} -> CHECK | invoice_line.amount_nok NUMERIC(12,2) NOT NULL CHECK (amount_nok >=0) |
| 93 | InvoiceLine.customerReference : String [0..1] | [0..1] -> nullable; String -> TEXT | invoice_line.customer_reference TEXT |
| 94 | class Payment | Class -> table with surrogate key | payment.id IDENTITY PK |
| 95 | Payment.paymentType : PaymentType [1] | [1] -> NOT NULL; PaymentType -> payment_type | payment.payment_type payment_type NOT NULL |
| 96 | Payment.amountNok : Money [1] {>0} | [1] -> NOT NULL; Money -> NUMERIC(12,2); {>0} -> CHECK | payment.amount_nok NUMERIC(12,2) NOT NULL CHECK (amount_nok >0) |
| 97 | Payment.vippsReference : String [1] {unique} | [1] -> NOT NULL; String -> TEXT; {unique} -> UNIQUE | payment.vipps_reference TEXT NOT NULL UNIQUE |
| 98 | Payment.status : PaymentStatus [1] | [1] -> NOT NULL; PaymentStatus -> payment_status | payment.status payment_status NOT NULL |
| 99 | Payment.paidAt : DateTime [0..1] | [0..1] -> nullable; DateTime -> TIMESTAMPTZ | payment.paid_at TIMESTAMPTZ |
| 100 | class DataSubjectRequest | Class -> table with surrogate key | data_subject_request.id IDENTITY PK |
| 101 | DataSubjectRequest.requestType : RequestType [1] | [1] -> NOT NULL; RequestType -> request_type | data_subject_request.request_type request_type NOT NULL |
| 102 | DataSubjectRequest.receivedAt : DateTime [1] | [1] -> NOT NULL; DateTime -> TIMESTAMPTZ | data_subject_request.received_at TIMESTAMPTZ NOT NULL |
| 103 | DataSubjectRequest.completedAt : DateTime [0..1] | [0..1] -> nullable; DateTime -> TIMESTAMPTZ | data_subject_request.completed_at TIMESTAMPTZ |
| 104 | class CapacityLimit | Class -> table with surrogate key | capacity_limit.id IDENTITY PK |
| 105 | CapacityLimit.validFrom : Date [1] {unique} | [1] -> NOT NULL; Date -> DATE; {unique} -> UNIQUE | capacity_limit.valid_from DATE NOT NULL UNIQUE |
| 106 | CapacityLimit.maxCoversPerDay : Integer [1] {>0} | [1] -> NOT NULL; Integer -> INTEGER; {>0} -> CHECK | capacity_limit.max_covers_per_day INTEGER NOT NULL CHECK (max_covers_per_day >0) |
| 107 | CapacityLimit.maxCoversWithWeddingDinner : Integer [1] {>0} | [1] -> NOT NULL; Integer -> INTEGER; {>0} -> CHECK | capacity_limit.max_covers_with_wedding_dinner INTEGER NOT NULL CHECK (max_covers_with_wedding_dinner >0) |
| 108 | CorporateCustomer "1" *-- "1..*" CompanyUser : has users | one-to-many -> FK in the 'many' table (company_user); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE CASCADE (composition: parts die with the whole); lower bound 1 on the 'many' end cannot be expressed by a FK -> deferred constraint trigger | company_user.corporate_customer_id -> corporate_customer.customer_id NOT NULL ON DELETE CASCADE |
| 109 | Customer "1" -- "0..*" Order : places | one-to-many -> FK in the 'many' table (customer_order); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE RESTRICT (referenced row cannot be deleted while in use) | customer_order.customer_id -> customer.id NOT NULL ON DELETE RESTRICT |
| 110 | CompanyUser "0..1" -- "0..*" Order : submits | one-to-many -> FK in the 'many' table (customer_order); lower bound 0 on the 'one' end -> nullable FK; ON DELETE SET NULL (optional link is cleared) | customer_order.company_user_id -> company_user.id ON DELETE SET NULL |
| 111 | Order "1" *-- "1..*" GuestGroup : consists of | one-to-many -> FK in the 'many' table (guest_group); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE CASCADE (composition: parts die with the whole); lower bound 1 on the 'many' end cannot be expressed by a FK -> deferred constraint trigger | guest_group.customer_order_id -> customer_order.id NOT NULL ON DELETE CASCADE |
| 112 | GuestGroup "0..*" -- "0..*" Allergen : has | many-to-many -> junction table guest_group_allergen with composite PK (no duplicate links); ON DELETE CASCADE from GuestGroup (owner end, left), RESTRICT from Allergen (cannot delete a Allergen that is in use) | TABLE guest_group_allergen |
| 113 | Order "1" *-- "1..*" OrderLine : contains | one-to-many -> FK in the 'many' table (order_line); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE CASCADE (composition: parts die with the whole); lower bound 1 on the 'many' end cannot be expressed by a FK -> deferred constraint trigger | order_line.customer_order_id -> customer_order.id NOT NULL ON DELETE CASCADE |
| 114 | OrderLine "0..*" -- "1" Dish : refers to | one-to-many -> FK in the 'many' table (order_line); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE RESTRICT (referenced row cannot be deleted while in use) | order_line.dish_id -> dish.id NOT NULL ON DELETE RESTRICT |
| 115 | Menu "0..*" -- "1..*" Dish : lists | many-to-many -> junction table menu_dish with composite PK (no duplicate links); ON DELETE CASCADE from Menu (owner end, left), RESTRICT from Dish (cannot delete a Dish that is in use); lower bound 1 (Menu needs >= 1 Dish) -> deferred constraint trigger | TABLE menu_dish |
| 116 | Dish "0..*" -- "0..*" Allergen : contains | many-to-many -> junction table dish_allergen with composite PK (no duplicate links); ON DELETE CASCADE from Dish (owner end, left), RESTRICT from Allergen (cannot delete a Allergen that is in use) | TABLE dish_allergen |
| 117 | Dish "0..*" -- "0..*" Ingredient : uses | many-to-many -> junction table dish_ingredient with composite PK (no duplicate links); ON DELETE CASCADE from Dish (owner end, left), RESTRICT from Ingredient (cannot delete a Ingredient that is in use) | TABLE dish_ingredient |
| 118 | Ingredient "0..*" -- "0..1" Supplier : supplied by | one-to-many -> FK in the 'many' table (ingredient); lower bound 0 on the 'one' end -> nullable FK; ON DELETE SET NULL (optional link is cleared) | ingredient.supplier_id -> supplier.id ON DELETE SET NULL |
| 119 | Order "1" *-- "0..1" AllergyConfirmation : confirmed by | one-to-one (1 : 0..1) -> FK in the optional side (allergy_confirmation) with UNIQUE so each Order has at most one AllergyConfirmation; NOT NULL because each AllergyConfirmation belongs to exactly one Order; ON DELETE CASCADE | allergy_confirmation.customer_order_id -> customer_order.id NOT NULL UNIQUE ON DELETE CASCADE |
| 120 | AllergyConfirmation "0..*" -- "1" StaffUser : given by | one-to-many -> FK in the 'many' table (allergy_confirmation); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE RESTRICT (referenced row cannot be deleted while in use) | allergy_confirmation.staff_user_id -> staff_user.id NOT NULL ON DELETE RESTRICT |
| 121 | CorporateCustomer "1" -- "0..*" StandingOrder : has | one-to-many -> FK in the 'many' table (standing_order); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE RESTRICT (referenced row cannot be deleted while in use) | standing_order.corporate_customer_id -> corporate_customer.customer_id NOT NULL ON DELETE RESTRICT |
| 122 | StandingOrder "1" *-- "1..*" StandingOrderLine : contains | one-to-many -> FK in the 'many' table (standing_order_line); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE CASCADE (composition: parts die with the whole); lower bound 1 on the 'many' end cannot be expressed by a FK -> deferred constraint trigger | standing_order_line.standing_order_id -> standing_order.id NOT NULL ON DELETE CASCADE |
| 123 | StandingOrderLine "0..*" -- "1" Dish : refers to | one-to-many -> FK in the 'many' table (standing_order_line); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE RESTRICT (referenced row cannot be deleted while in use) | standing_order_line.dish_id -> dish.id NOT NULL ON DELETE RESTRICT |
| 124 | StandingOrder "0..1" -- "0..*" Order : generates | one-to-many -> FK in the 'many' table (customer_order); lower bound 0 on the 'one' end -> nullable FK; ON DELETE SET NULL (optional link is cleared) | customer_order.standing_order_id -> standing_order.id ON DELETE SET NULL |
| 125 | Customer "1" -- "0..*" Invoice : is billed | one-to-many -> FK in the 'many' table (invoice); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE RESTRICT (referenced row cannot be deleted while in use) | invoice.customer_id -> customer.id NOT NULL ON DELETE RESTRICT |
| 126 | Invoice "1" *-- "1..*" InvoiceLine : contains | one-to-many -> FK in the 'many' table (invoice_line); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE CASCADE (composition: parts die with the whole); lower bound 1 on the 'many' end cannot be expressed by a FK -> deferred constraint trigger | invoice_line.invoice_id -> invoice.id NOT NULL ON DELETE CASCADE |
| 127 | InvoiceLine "0..1" -- "1" Order : bills | one-to-one (0..1 : 1) -> FK in the optional side (invoice_line) with UNIQUE so each Order has at most one InvoiceLine; NOT NULL because each InvoiceLine belongs to exactly one Order; ON DELETE RESTRICT | invoice_line.customer_order_id -> customer_order.id NOT NULL UNIQUE ON DELETE RESTRICT |
| 128 | Order "1" -- "0..*" Payment : is paid by | one-to-many -> FK in the 'many' table (payment); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE RESTRICT (referenced row cannot be deleted while in use) | payment.customer_order_id -> customer_order.id NOT NULL ON DELETE RESTRICT |
| 129 | Customer "1" -- "0..*" DataSubjectRequest : submits | one-to-many -> FK in the 'many' table (data_subject_request); lower bound 1 on the 'one' end -> NOT NULL FK; ON DELETE RESTRICT (referenced row cannot be deleted while in use) | data_subject_request.customer_id -> customer.id NOT NULL ON DELETE RESTRICT |
| 130 | abstract class Customer | Abstract -> every row must have exactly one subtype row: discriminator column + deferred trigger | customer.customer_type + trigger |
| 131 | every FK column | PostgreSQL does not index FK columns automatically -> one index per FK (not needed where UNIQUE/PK already indexes it) | CREATE INDEX ..._idx |

## Not mapped / limitations

- **CapacityLimit** is a standalone table; whether limits block or warn is unresolved (ISS-06).
- **Personal-data deletion (US-31):** RESTRICT on `customer` means a customer with orders cannot be deleted. Deletion must anonymise personal fields instead, because bookkeeping data is kept for 5 years (GDPR note). This is a design decision for the PO, not modelled in the class diagram.
- **State transitions:** the database stores `status` but does not enforce the allowed transitions from the state machine; that belongs in application logic or a trigger in a later iteration.

## Live test against PostgreSQL

Each test runs in its own transaction against the generated schema. A rejection only counts as a pass when the error is the expected one.

| Test | Description | Expected | Actual | Pass | Database message |
|---|---|---|---|---|---|
| DDL | Generated schema executes | accepted | accepted | yes |  |
| T01 | Valid private customer with an order, guest group, line, menu and dish | accepted | accepted | yes |  |
| T02 | Order without any guest group (Order 1 *-- 1..* GuestGroup) | rejected | rejected | yes | Multiplicity violated: Order must have at least 1 GuestGroup (id 1001) |
| T03 | Corporate subtype row for a PRIVATE customer (inheritance discriminator) | rejected | rejected | yes | insert or update on table "corporate_customer" violates foreign key constraint "corporate_customer_customer_id_customer_type_fkey" |
| T04 | Guest group with guestCount 0 ({>0}) | rejected | rejected | yes | new row for relation "guest_group" violates check constraint "guest_group_guest_count_check" |
| T05 | Second invoice line for the same order (InvoiceLine 0..1 -- 1 Order) | rejected | rejected | yes | duplicate key value violates unique constraint "invoice_line_customer_order_id_key" |
| T06 | Delete a customer who has orders (RESTRICT) | rejected | rejected | yes | update or delete on table "customer" violates foreign key constraint "customer_order_customer_id_fkey" on table "customer_order" |
| T07 | Second allergy confirmation for the same order (1 -- 0..1) | rejected | rejected | yes | duplicate key value violates unique constraint "allergy_confirmation_customer_order_id_key" |
| T08 | Delete an allergen that a dish uses (junction RESTRICT) | rejected | rejected | yes | update or delete on table "allergen" violates foreign key constraint "dish_allergen_allergen_id_fkey" on table "dish_allergen" |
| T09 | Customer row without subtype row (abstract Customer) | rejected | rejected | yes | Abstract class Customer: id 1001 has no subtype row |
| T10 | Menu without dishes (Menu 0..* -- 1..* Dish) | rejected | rejected | yes | Multiplicity violated: Menu must have at least 1 Dish (id 1001) |
| T11 | Deleting an order removes its guest groups and lines (composition CASCADE) | accepted | accepted | yes |  |
