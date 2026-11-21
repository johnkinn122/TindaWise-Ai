def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_create_product_records_opening_stock(client, headers, make_product):
    product = make_product(name="Lucky Me Pancit Canton", initial_stock=12)

    assert product["stock_on_hand"] == 12
    assert product["currency"] == "PHP"
    movements = client.get(f"/api/v1/products/{product['id']}/movements", headers=headers).json()
    assert movements["total"] == 1
    assert movements["items"][0]["reason"] == "initial"
    assert movements["items"][0]["balance_after"] == 12


def test_money_is_exact_decimal(make_product):
    product = make_product(price="16.10", cost="13.35")
    # Decimals are serialized as strings, so no float rounding (16.1 vs 16.099999...).
    assert product["price"] == "16.10"
    assert product["cost"] == "13.35"


def test_validation_errors_point_at_fields(client, headers):
    response = client.post(
        "/api/v1/products", json={"name": "", "sku": "X", "price": "-1"}, headers=headers
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert "price" in body["fields"]
    assert "name" in body["fields"]


def test_price_rejects_more_than_two_decimals(client, headers):
    response = client.post(
        "/api/v1/products", json={"name": "A", "sku": "A", "price": "1.005"}, headers=headers
    )
    assert response.status_code == 422
    assert "price" in response.json()["error"]["fields"]


def test_duplicate_sku_is_a_conflict(client, headers, make_product):
    make_product(sku="NDL-001")
    response = client.post(
        "/api/v1/products", json={"name": "Other", "sku": "NDL-001", "price": "1"}, headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["fields"] == {"sku": "Already used by another product"}


def test_duplicate_barcode_is_a_conflict_but_blank_barcodes_are_fine(client, headers, make_product):
    make_product(barcode="2000000000015")
    make_product(barcode="")  # blank → stored as NULL
    make_product(barcode=None)  # two products without barcodes are allowed

    response = client.post(
        "/api/v1/products",
        json={"name": "Dup", "sku": "DUP", "price": "1", "barcode": "2000000000015"},
        headers=headers,
    )
    assert response.status_code == 409
    assert "barcode" in response.json()["error"]["fields"]


def test_list_search_filter_sort_and_paginate(client, headers, make_product):
    make_product(name="Coca-Cola 1.5L", sku="BEV-001", initial_stock=0)
    make_product(name="Bear Brand Swak", sku="DRY-001", initial_stock=3, reorder_level=10)
    make_product(name="Datu Puti Vinegar", sku="CND-001", initial_stock=40, reorder_level=5)

    def get(**params):
        return client.get("/api/v1/products", params=params, headers=headers).json()

    assert get()["total"] == 3
    assert [p["name"] for p in get(q="cola")["items"]] == ["Coca-Cola 1.5L"]
    assert [p["sku"] for p in get(q="dry-")["items"]] == ["DRY-001"]
    assert [p["name"] for p in get(status="out_of_stock")["items"]] == ["Coca-Cola 1.5L"]
    assert [p["name"] for p in get(status="low_stock")["items"]] == ["Bear Brand Swak"]
    assert [p["name"] for p in get(status="in_stock")["items"]] == ["Datu Puti Vinegar"]
    assert [p["stock_on_hand"] for p in get(sort="-stock")["items"]] == [40, 3, 0]

    page = get(limit=2, offset=2)
    assert page["total"] == 3
    assert len(page["items"]) == 1


def test_search_treats_wildcards_literally(client, headers, make_product):
    make_product(name="Promo 50% off")
    make_product(name="Plain item")
    items = client.get("/api/v1/products", params={"q": "50%"}, headers=headers).json()["items"]
    assert [p["name"] for p in items] == ["Promo 50% off"]


def test_update_product(client, headers, make_product):
    product = make_product()
    response = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"name": "Renamed", "price": "12.50"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    assert response.json()["price"] == "12.50"
    assert response.json()["stock_on_hand"] == product["stock_on_hand"]


def test_update_cannot_blank_a_required_field(client, headers, make_product):
    product = make_product()
    response = client.patch(
        f"/api/v1/products/{product['id']}", json={"name": None}, headers=headers
    )
    assert response.status_code == 422


def test_archive_hides_product_but_keeps_it(client, headers, make_product):
    product = make_product()
    assert client.delete(f"/api/v1/products/{product['id']}", headers=headers).status_code == 204

    assert client.get("/api/v1/products", headers=headers).json()["total"] == 0
    archived = client.get(
        "/api/v1/products", params={"include_archived": True}, headers=headers
    ).json()
    assert archived["items"][0]["is_active"] is False


def test_categories(client, headers, make_product):
    created = client.post("/api/v1/categories", json={"name": "Noodles"}, headers=headers)
    assert created.status_code == 201
    duplicate = client.post("/api/v1/categories", json={"name": "Noodles"}, headers=headers)
    assert duplicate.status_code == 409

    product = make_product(category_id=created.json()["id"])
    assert product["category"]["name"] == "Noodles"
