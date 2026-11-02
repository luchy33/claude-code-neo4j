from typing import Optional

from app.models.enums import Allergen, DietaryLabel, EventCategory
from app.models.errors import FoodItemInUseError
from app.models.food_item import FoodItem
from app.models.repositories.db import next_ids, query, write

# attribute on FoodItem -> (relationship type, value node label, enum class)
VALUE_SETS = {
    "categories": ("SUITABLE_FOR", "EventCategory", EventCategory),
    "allergens": ("CONTAINS", "Allergen", Allergen),
    "dietary_labels": ("HAS_LABEL", "DietaryLabel", DietaryLabel),
}

# The item's properties plus its value sets, read in the same query.
ITEM = "f {.*, " + ", ".join(f"{attr}: [(f)-[:{rel}]->(v:{label}) | v.value]"
                             for attr, (rel, label, _) in VALUE_SETS.items()) + "} AS item"


class FoodItemRepository:
    def add(self, item: FoodItem) -> FoodItem:
        def create(tx):
            [item_id] = next_ids(tx, "FoodItem")
            tx.run("CREATE (f:FoodItem {id: $id}) SET f += $props", id=item_id, props=self._props(item)).consume()
            self._write_value_sets(tx, item_id, item)
            return item_id

        item.id = write(create)
        return item

    def update(self, item: FoodItem) -> None:
        def save(tx):
            tx.run("MATCH (f:FoodItem {id: $id}) SET f += $props", id=item.id, props=self._props(item)).consume()
            self._write_value_sets(tx, item.id, item)

        write(save)

    def set_image(self, item_id: int, filename: Optional[str]) -> None:
        query("MATCH (f:FoodItem {id: $id}) SET f.image_filename = $filename", id=item_id, filename=filename)

    def delete(self, item_id: int) -> None:
        if query("MATCH (:OrderLine)-[:OF_ITEM]->(f:FoodItem {id: $id}) RETURN f LIMIT 1", id=item_id):
            raise FoodItemInUseError("This food item is part of existing orders.")
        query("MATCH (f:FoodItem {id: $id}) DETACH DELETE f", id=item_id)

    def get(self, item_id: int) -> Optional[FoodItem]:
        records = query(f"MATCH (f:FoodItem {{id: $id}}) RETURN {ITEM}", id=item_id)
        return self._to_item(records[0]["item"]) if records else None

    def get_many(self, ids) -> dict[int, FoodItem]:
        ids = list(ids)
        if not ids:
            return {}
        records = query(f"MATCH (f:FoodItem) WHERE f.id IN $ids RETURN {ITEM}", ids=ids)
        return {r["item"]["id"]: self._to_item(r["item"]) for r in records}

    def list_all(self, published_only: bool = False) -> list[FoodItem]:
        where = " WHERE f.published" if published_only else ""
        records = query(f"MATCH (f:FoodItem){where} RETURN {ITEM} ORDER BY f.name_en")
        return [self._to_item(r["item"]) for r in records]

    def list_by_category(self, category: EventCategory) -> list[FoodItem]:
        records = query(f"MATCH (f:FoodItem)-[:SUITABLE_FOR]->(:EventCategory {{value: $value}})"
                        f" WHERE f.published RETURN {ITEM} ORDER BY f.name_en", value=category.value)
        return [self._to_item(r["item"]) for r in records]

    @staticmethod
    def _props(item: FoodItem) -> dict:
        return {"name_en": item.name_en, "name_no": item.name_no, "description": item.description,
                "price_nok": item.price_nok, "min_order_quantity": item.min_order_quantity,
                "image_filename": item.image_filename, "published": item.published}

    @staticmethod
    def _write_value_sets(tx, item_id: int, item: FoodItem) -> None:
        """Replace the item's links to the fixed value nodes."""
        for attr, (rel, label, _) in VALUE_SETS.items():
            tx.run(f"MATCH (f:FoodItem {{id: $id}})-[r:{rel}]->() DELETE r", id=item_id).consume()
            tx.run(f"MATCH (f:FoodItem {{id: $id}}) UNWIND $values AS value"
                   f" MATCH (v:{label} {{value: value}}) MERGE (f)-[:{rel}]->(v)",
                   id=item_id, values=[v.value for v in getattr(item, attr)]).consume()

    @staticmethod
    def _to_item(data) -> FoodItem:
        sets = {attr: {enum(value) for value in data[attr]} for attr, (_, _, enum) in VALUE_SETS.items()}
        return FoodItem(
            id=data["id"],
            name_en=data["name_en"],
            name_no=data["name_no"],
            description=data["description"],
            price_nok=data["price_nok"],
            min_order_quantity=data["min_order_quantity"],
            image_filename=data.get("image_filename"),
            published=data["published"],
            **sets,
        )
