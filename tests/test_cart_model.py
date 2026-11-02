import pytest

from app.models import Cart, CartError, EventCategory, FoodItem


def dish(item_id, minimum=10, price=100, published=True, name=None):
    return FoodItem(id=item_id, name_en=name or f"Dish {item_id}", name_no="Rett", price_nok=price,
                    categories={EventCategory.OTHER}, min_order_quantity=minimum, published=published)


def test_add_at_or_above_minimum():
    cart = Cart()
    cart.add(dish(1, minimum=10), 10)
    cart.add(dish(2, minimum=10), 25)

    assert cart.quantities == {1: 10, 2: 25}
    assert cart.item_count == 2 and not cart.is_empty


def test_add_below_minimum_is_refused():
    cart = Cart()
    with pytest.raises(CartError, match="minimum order is 10 portions"):
        cart.add(dish(1, minimum=10), 9)
    assert cart.is_empty


def test_adding_same_dish_twice_adds_quantities():
    cart = Cart()
    item = dish(1, minimum=10)
    cart.add(item, 10)
    cart.add(item, 5)  # 5 alone is below the minimum, but the line becomes 15

    assert cart.quantities == {1: 15}


def test_set_quantity_rules():
    item = dish(1, minimum=10)
    cart = Cart({1: 10})

    cart.set_quantity(item, 40)
    assert cart.quantities == {1: 40}

    with pytest.raises(CartError, match="minimum"):
        cart.set_quantity(item, 9)
    with pytest.raises(CartError, match="at most"):
        cart.set_quantity(item, Cart.MAX_QUANTITY + 1)
    assert cart.quantities == {1: 40}  # unchanged after refused changes

    cart.set_quantity(item, 0)
    assert cart.is_empty


def test_unpublished_dish_cannot_be_added():
    with pytest.raises(CartError, match="no longer on the menu"):
        Cart().add(dish(1, published=False), 20)


def test_remove():
    cart = Cart({1: 10, 2: 12})
    cart.remove(1)
    cart.remove(99)  # unknown id is ignored

    assert cart.quantities == {2: 12}


def test_lines_and_total_use_current_prices():
    cart = Cart({1: 10, 2: 3})
    items = {1: dish(1, price=189, name="Fish soup"), 2: dish(2, minimum=1, price=95, name="Cake")}

    lines, removed = cart.lines(items)

    assert removed == []
    assert [(l.food_item.name_en, l.quantity, l.line_total_nok) for l in lines] == [
        ("Cake", 3, 285), ("Fish soup", 10, 1890)]
    assert Cart.total_nok(lines) == 2175


def test_lines_drop_missing_and_unpublished_dishes():
    cart = Cart({1: 10, 2: 10, 3: 10})
    items = {1: dish(1), 2: dish(2, published=False, name="Hidden stew")}

    lines, removed = cart.lines(items)

    assert [l.food_item.id for l in lines] == [1]
    assert "Hidden stew" in removed and len(removed) == 2
    assert cart.quantities == {1: 10}
