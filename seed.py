"""Reset the database and fill it with synthetic data.

Usage: python seed.py
WARNING: drops all tables first. Synthetic data only – no real customers.
"""
import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from app import create_app
from app.models import (Allergen as A, Customer, DeliveryMethod, DietaryLabel as D,
                        EventCategory as E, FoodItem, GuestGroup, Order, OrderLine,
                        OrderStatus as S, PaymentStatus as P, Question)
from app.models.repositories import (CustomerRepository, FoodItemRepository, ImageStore, OrderRepository,
                                     QuestionRepository)
from app.models.repositories.db import init_db

DEV_PASSWORD = "ektemat-dev"

# Front picture per dish (English name -> file in seed_data/images/), chosen by the team.
SEED_IMAGE_DIR = Path(__file__).parent / "seed_data" / "images"
FOOD_IMAGES = {
    "Fish soup with Bergen cod": "fish-soup.webp",
    "Slow-cooked lamb from Voss": "slow-cooked-lamb.jpg",
    "Beetroot and chickpea salad": "beetroot-chickpea-salad.jpg",
    "Rakfisk tasting": "rakfisk.jpg",
    "Pinnekjøtt Christmas dinner": "pinnekjott.jpg",
    "Tapas platter": "tapas-platter.jpg",
    "Three-course wedding dinner": "three-course-wedding-dinner.jpg",
    "Kransekake (almond ring cake)": "kransekake.jpg",
    "Coffee and cake": "coffee-and-cake.jpg",
}

# Lunch dishes follow the autumn menu draft in
# labb_claude_cowork/docs/04_Data/04_reference_lunch-menu-autumn_2026-10-20.txt
FOOD_ITEMS = [
    FoodItem("Fish soup with Bergen cod", "Fiskesuppe med Bergens-torsk", 189,
             {E.LUNCH_MEETING, E.CONFERENCE}, "Root vegetables and sourdough bread.", 10,
             {A.FISH, A.MILK, A.GLUTEN, A.CELERY}),
    FoodItem("Slow-cooked lamb from Voss", "Sakte-kokt lam fra Voss", 245,
             {E.LUNCH_MEETING, E.CONFERENCE, E.CONFIRMATION}, "Served with barley risotto.", 10,
             {A.MILK, A.GLUTEN, A.CELERY}),
    FoodItem("Beetroot and chickpea salad", "Rødbete- og kikertsalat", 165,
             {E.LUNCH_MEETING, E.CONFERENCE, E.BIRTHDAY}, "With goat cheese from Hardanger.", 8,
             {A.MILK, A.MUSTARD}, {D.VEGETARIAN, D.GLUTEN_FREE}),
    FoodItem("Rakfisk tasting", "Rakfisk-smaking", 210,
             {E.CHRISTMAS_PARTY}, "Seasonal, November only.", 12, {A.FISH, A.MILK}),
    FoodItem("Pinnekjøtt Christmas dinner", "Pinnekjøtt med kålrabistappe", 395,
             {E.CHRISTMAS_PARTY}, "Salted, dried lamb ribs with swede mash and potatoes.", 15,
             {A.MILK, A.CELERY}, {D.GLUTEN_FREE}),
    FoodItem("Tapas platter", "Tapasbord", 225,
             {E.BIRTHDAY, E.CONFIRMATION, E.OTHER}, "Cured meats, cheeses, olives and bread.", 10,
             {A.MILK, A.GLUTEN, A.NUTS}),
    FoodItem("Three-course wedding dinner", "Treretters bryllupsmiddag", 695,
             {E.WEDDING}, "Starter, main course with local lamb or fish, and dessert.", 30,
             {A.FISH, A.MILK, A.GLUTEN, A.NUTS, A.EGGS}),
    FoodItem("Kransekake (almond ring cake)", "Kransekake", 95,
             {E.WEDDING, E.CONFIRMATION}, "Traditional almond cake, serves one per portion.", 20,
             {A.NUTS, A.EGGS}, {D.GLUTEN_FREE, D.LACTOSE_FREE}),
    FoodItem("Coffee and cake", "Kaffe og kake", 85,
             {E.BIRTHDAY, E.CONFIRMATION, E.CONFERENCE, E.OTHER}, "Coffee, tea and homemade cake.", 10,
             {A.MILK, A.GLUTEN, A.EGGS}, {D.VEGETARIAN}),
    FoodItem("Vegan lentil stew", "Vegansk linsegryte", 155,
             {E.LUNCH_MEETING, E.CONFERENCE}, "Draft dish – not yet on the menu.", 10,
             set(), {D.VEGAN, D.VEGETARIAN, D.GLUTEN_FREE, D.LACTOSE_FREE}, published=False),
]


def main() -> None:
    password = os.environ.get("SEED_PASSWORD")
    if not password:
        password = DEV_PASSWORD
        print(f"SEED_PASSWORD not set – using the dev default '{DEV_PASSWORD}'.")

    app = create_app()
    with app.app_context():
        print(f"Resetting database at {app.config['DATABASE']} (all data and uploaded images are deleted).")
        init_db()
        shutil.rmtree(app.config["UPLOAD_FOLDER"], ignore_errors=True)  # images belonged to the old data

        food_repo = FoodItemRepository()
        for item in FOOD_ITEMS:
            food_repo.add(item)

        store = ImageStore()
        for item in FOOD_ITEMS:
            image_name = FOOD_IMAGES.get(item.name_en)
            if image_name:
                data = (SEED_IMAGE_DIR / image_name).read_bytes()
                ext = ImageStore.validate_upload(image_name, data)  # same checks as an admin upload
                item.image_filename = store.promote(store.save_pending(data, ext), item.id)
                food_repo.set_image(item.id, item.image_filename)

        customer_repo = CustomerRepository()
        admin = Customer("Ekte Mat Admin", "admin@ektemat.example", is_admin=True)
        private = Customer("Test Private Customer", "private.customer@example.com", phone="+47 400 00 001")
        corporate = Customer("Test Corporate Customer AS", "lunch@corporate.example.com",
                             customer_type="corporate", organisation_number="999999999",
                             phone="+47 400 00 002")
        for customer in (admin, private, corporate):
            customer.set_password(password)
            customer_repo.add(customer)

        # Demo orders covering every status and payment status (A3 filters, C4 and report screenshots).
        dish = {item.name_en: item for item in FOOD_ITEMS}
        today = date.today()
        orders = OrderRepository()
        demo_orders = [
            # customer, event, days from today, status, payment, groups, (dish, portions)
            (corporate, E.LUNCH_MEETING, 14, S.SUBMITTED, P.NOT_PAID,
             [GuestGroup(10, "Main group"), GuestGroup(2, "Gluten free", "2 guests: gluten free")],
             [("Fish soup with Bergen cod", 12)]),
            (private, E.CONFIRMATION, 30, S.APPROVED, P.DEPOSIT_PAID,
             [GuestGroup(25, "Family"), GuestGroup(3, "Vegetarians", "Vegetarian, one with nut allergy")],
             [("Slow-cooked lamb from Voss", 25), ("Beetroot and chickpea salad", 8), ("Kransekake (almond ring cake)", 28)]),
            (corporate, E.CONFERENCE, 3, S.IN_PREPARATION, P.INVOICED,
             [GuestGroup(40, "Participants"), GuestGroup(4, "Lactose free", "Lactose intolerance")],
             [("Coffee and cake", 44), ("Fish soup with Bergen cod", 40)]),
            (private, E.BIRTHDAY, -10, S.DELIVERED, P.PAID,
             [GuestGroup(15)],
             [("Tapas platter", 15), ("Coffee and cake", 15)]),
            (corporate, E.CHRISTMAS_PARTY, 45, S.CANCELLED, P.NOT_PAID,
             [GuestGroup(30, "Staff")],
             [("Pinnekjøtt Christmas dinner", 30)]),
        ]
        saved = []
        for customer, event, days, status, payment, groups, dishes in demo_orders:
            saved.append(orders.add(Order(
                order_number="", customer_id=customer.id, event_type=event,
                event_date=today + timedelta(days=days),
                delivery_method=DeliveryMethod.DELIVERY if customer is corporate else DeliveryMethod.PICK_UP,
                delivery_address="Testgaten 1, 5003 Bergen" if customer is corporate else None,
                status=status, payment_status=payment, guest_groups=groups,
                lines=[OrderLine(dish[name].id, qty, dish[name].price_nok) for name, qty in dishes],
            )))

        # Demo questions (C5/A4): one answered, two waiting for an answer.
        lunch, confirmation, conference = saved[0], saved[1], saved[2]
        questions = QuestionRepository()
        answered = Question.for_order(confirmation, private, "Delivery time",
                                      "Can you deliver at 17:00 instead of picking up? The party starts at 18:00.")
        answered.give_answer("Yes, delivery at 17:00 is fine. We will add the delivery fee to the invoice.",
                             datetime.now())
        demo_questions = [
            answered,
            Question.for_order(lunch, corporate, "Gluten-free bread",
                               "Can the two gluten-free guests get gluten-free bread with the fish soup?"),
            Question.for_order(conference, corporate, "Extra participants",
                               "We may be 4 more participants. Can we change the number until the day before?"),
        ]
        for question in demo_questions:
            questions.add(question)

    print(f"Seeded {len(FOOD_ITEMS)} food items (1 unpublished, {len(FOOD_IMAGES)} with pictures), "
          f"3 customers (1 admin), {len(demo_orders)} demo orders and {len(demo_questions)} demo questions.")


if __name__ == "__main__":
    main()
