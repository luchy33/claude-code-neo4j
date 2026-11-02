"""Neo4j storage (plan 06): the graph the repositories write, ids, constraints and init_db."""
import pytest
from neo4j.exceptions import ConstraintError

from app.models import Allergen, Customer, DietaryLabel, EventCategory, FoodItem, Question
from app.models.repositories import CustomerRepository, FoodItemRepository, OrderRepository, QuestionRepository
from app.models.repositories.db import init_db, query


def test_food_item_value_sets_are_relationships_to_shared_value_nodes(app):
    with app.app_context():
        repo = FoodItemRepository()
        soup = repo.add(FoodItem("Fish soup", "Fiskesuppe", 189, {EventCategory.LUNCH_MEETING},
                                 allergens={Allergen.FISH, Allergen.MILK}))
        repo.add(FoodItem("Salad", "Salat", 165, {EventCategory.LUNCH_MEETING},
                          dietary_labels={DietaryLabel.VEGAN}))

        allergens = query("MATCH (:FoodItem {id: $id})-[:CONTAINS]->(a:Allergen) RETURN a.value AS v", id=soup.id)
        assert {r["v"] for r in allergens} == {"fish", "milk"}
        # Both dishes point at the same event category node instead of each storing a copy.
        shared = query("MATCH (f:FoodItem)-[:SUITABLE_FOR]->(e:EventCategory {value: 'lunch_meeting'})"
                       " RETURN count(DISTINCT e) AS nodes, count(f) AS dishes")[0]
        assert (shared["nodes"], shared["dishes"]) == (1, 2)


def test_update_replaces_value_sets_and_clears_removed_properties(app):
    with app.app_context():
        repo = FoodItemRepository()
        item = repo.add(FoodItem("Fish soup", "Fiskesuppe", 189, {EventCategory.LUNCH_MEETING},
                                 allergens={Allergen.FISH}, image_filename="1-" + "a" * 32 + ".jpg"))
        item.categories = {EventCategory.CONFERENCE}
        item.allergens = set()
        item.image_filename = None
        repo.update(item)

        saved = repo.get(item.id)
        assert saved.categories == {EventCategory.CONFERENCE}
        assert saved.allergens == set()
        assert saved.image_filename is None


def test_order_and_question_are_connected_in_the_graph(app, customer, make_order, food_item):
    order = make_order(customer)
    with app.app_context():
        QuestionRepository().add(Question.for_order(order, customer, "Bread", "Gluten-free bread?"))

        path = query("MATCH (c:Customer {id: $customer_id})-[:PLACED]->(o:Order {id: $order_id})"
                     "-[:HAS_LINE]->(:OrderLine)-[:OF_ITEM]->(f:FoodItem),"
                     " (o)-[:FOR_EVENT]->(:EventCategory {value: 'lunch_meeting'}),"
                     " (c)-[:ASKED]->(:Question)-[:ABOUT]->(o)"
                     " RETURN f.id AS item", customer_id=customer.id, order_id=order.id)
        assert [r["item"] for r in path] == [food_item.id]
        groups = query("MATCH (:Order {id: $id})-[:HAS_GUEST_GROUP]->(g) RETURN count(g) AS n", id=order.id)
        assert groups[0]["n"] == 2


def test_ids_are_unique_integers_per_label(app, customer, make_order):
    first, second = make_order(customer), make_order(customer)
    assert isinstance(first.id, int) and second.id == first.id + 1
    line_ids = [line.id for order in (first, second) for line in order.lines]
    group_ids = [group.id for order in (first, second) for group in order.guest_groups]
    assert len(set(line_ids)) == len(line_ids) and len(set(group_ids)) == len(group_ids)


def test_order_for_unknown_customer_is_not_saved(app, customer, make_order):
    with pytest.raises(ValueError):
        make_order(Customer("Ghost", "ghost@example.com", id=999))
    with app.app_context():
        assert OrderRepository().list_all() == []


def test_duplicate_email_is_rejected_by_constraint(app, customer):
    with app.app_context(), pytest.raises(ConstraintError):
        CustomerRepository().add(Customer("Copy", customer.email))


def test_init_db_can_run_twice_and_empties_the_database(app, customer):
    with app.app_context():
        init_db()
        init_db()
        assert CustomerRepository().list_all() == []
        values = query("MATCH (e:EventCategory) RETURN count(e) AS n")[0]["n"]
        assert values == len(EventCategory)
