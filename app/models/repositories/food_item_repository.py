from typing import Optional

from app.models.enums import Allergen, DietaryLabel, EventCategory
from app.models.errors import FoodItemInUseError
from app.models.food_item import FoodItem
from app.models.repositories.db import get_db

# attribute on FoodItem -> (join table, enum class)
VALUE_SETS = {
    "categories": ("food_item_category", EventCategory),
    "allergens": ("food_item_allergen", Allergen),
    "dietary_labels": ("food_item_dietary_label", DietaryLabel),
}


class FoodItemRepository:
    def add(self, item: FoodItem) -> FoodItem:
        db = get_db()
        with db:
            cur = db.execute(
                "INSERT INTO food_item (name_en, name_no, description, price_nok, min_order_quantity,"
                " image_filename, published) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (item.name_en, item.name_no, item.description, item.price_nok,
                 item.min_order_quantity, item.image_filename, int(item.published)),
            )
            item.id = cur.lastrowid
            self._write_value_sets(item)
        return item

    def update(self, item: FoodItem) -> None:
        db = get_db()
        with db:
            db.execute(
                "UPDATE food_item SET name_en = ?, name_no = ?, description = ?, price_nok = ?,"
                " min_order_quantity = ?, image_filename = ?, published = ? WHERE id = ?",
                (item.name_en, item.name_no, item.description, item.price_nok,
                 item.min_order_quantity, item.image_filename, int(item.published), item.id),
            )
            self._write_value_sets(item)

    def set_image(self, item_id: int, filename: Optional[str]) -> None:
        db = get_db()
        db.execute("UPDATE food_item SET image_filename = ? WHERE id = ?", (filename, item_id))
        db.commit()

    def delete(self, item_id: int) -> None:
        db = get_db()
        in_use = db.execute("SELECT 1 FROM order_line WHERE food_item_id = ? LIMIT 1", (item_id,)).fetchone()
        if in_use:
            raise FoodItemInUseError("This food item is part of existing orders.")
        with db:
            db.execute("DELETE FROM food_item WHERE id = ?", (item_id,))

    def get(self, item_id: int) -> Optional[FoodItem]:
        row = get_db().execute("SELECT * FROM food_item WHERE id = ?", (item_id,)).fetchone()
        return self._to_item(row) if row else None

    def get_many(self, ids) -> dict[int, FoodItem]:
        ids = list(ids)
        if not ids:
            return {}
        placeholders = ", ".join("?" * len(ids))
        rows = get_db().execute(f"SELECT * FROM food_item WHERE id IN ({placeholders})", ids).fetchall()
        return {row["id"]: self._to_item(row) for row in rows}

    def list_all(self, published_only: bool = False) -> list[FoodItem]:
        sql = "SELECT * FROM food_item"
        if published_only:
            sql += " WHERE published = 1"
        rows = get_db().execute(sql + " ORDER BY name_en").fetchall()
        return [self._to_item(r) for r in rows]

    def list_by_category(self, category: EventCategory) -> list[FoodItem]:
        rows = get_db().execute(
            "SELECT f.* FROM food_item f JOIN food_item_category c ON c.food_item_id = f.id"
            " WHERE c.value = ? AND f.published = 1 ORDER BY f.name_en",
            (category.value,),
        ).fetchall()
        return [self._to_item(r) for r in rows]

    def _write_value_sets(self, item: FoodItem) -> None:
        db = get_db()
        for attr, (table, _) in VALUE_SETS.items():
            db.execute(f"DELETE FROM {table} WHERE food_item_id = ?", (item.id,))
            db.executemany(f"INSERT INTO {table} (food_item_id, value) VALUES (?, ?)",
                           [(item.id, v.value) for v in getattr(item, attr)])

    def _to_item(self, row) -> FoodItem:
        db = get_db()
        sets = {
            attr: {enum(r["value"]) for r in db.execute(f"SELECT value FROM {table} WHERE food_item_id = ?",
                                                         (row["id"],))}
            for attr, (table, enum) in VALUE_SETS.items()
        }
        return FoodItem(
            id=row["id"],
            name_en=row["name_en"],
            name_no=row["name_no"],
            description=row["description"],
            price_nok=row["price_nok"],
            min_order_quantity=row["min_order_quantity"],
            image_filename=row["image_filename"],
            published=bool(row["published"]),
            **sets,
        )
