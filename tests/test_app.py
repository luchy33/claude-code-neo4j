def test_shop_index_lists_food_items(client, food_item):
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Fish soup" in html
    assert "189 NOK" in html
    assert "Minimum order: 10" in html
    assert "Lunch meeting" in html
