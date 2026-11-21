"""One organization must never see or change another organization's data."""


def test_other_org_cannot_see_or_touch_products(client, headers, other_headers, make_product):
    product = make_product()
    url = f"/api/v1/products/{product['id']}"

    assert client.get("/api/v1/products", headers=other_headers).json()["total"] == 0
    assert client.get(url, headers=other_headers).status_code == 404
    assert client.patch(url, json={"name": "x"}, headers=other_headers).status_code == 404
    assert client.delete(url, headers=other_headers).status_code == 404
    assert client.get(f"{url}/movements", headers=other_headers).status_code == 404
    adjustment = client.post(
        f"{url}/stock-adjustments",
        json={"quantity_change": -1, "reason": "sale"},
        headers=other_headers,
    )
    assert adjustment.status_code == 404
    assert client.get(url, headers=headers).json()["stock_on_hand"] == product["stock_on_hand"]


def test_cannot_use_another_orgs_category(client, headers, other_headers):
    category = client.post("/api/v1/categories", json={"name": "Snacks"}, headers=headers).json()
    response = client.post(
        "/api/v1/products",
        json={"name": "x", "sku": "x", "price": "1", "category_id": category["id"]},
        headers=other_headers,
    )
    assert response.status_code == 404


def test_same_sku_is_allowed_in_different_orgs(client, headers, other_headers):
    payload = {"name": "Coke", "sku": "BEV-001", "price": "80"}
    assert client.post("/api/v1/products", json=payload, headers=headers).status_code == 201
    assert client.post("/api/v1/products", json=payload, headers=other_headers).status_code == 201


def test_the_old_organization_header_grants_nothing(client, org):
    response = client.get("/api/v1/products", headers={"X-Organization-Id": str(org.id)})
    assert response.status_code == 401
