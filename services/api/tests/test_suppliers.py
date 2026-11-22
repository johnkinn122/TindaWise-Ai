from app.models import Role
from tests.conftest import auth_headers

URL = "/api/v1/suppliers"


def add(client, headers, **fields):
    return client.post(URL, json={"name": "Puregold Wholesale"} | fields, headers=headers)


def test_create_list_and_search(client, headers):
    created = add(client, headers, contact_name="Ana Cruz", phone="0917 555 0101", email="")
    assert created.status_code == 201, created.text
    assert created.json()["email"] is None  # blank optional fields are stored as null
    add(client, headers, name="Alaska Dairy Distributor")

    names = [s["name"] for s in client.get(URL, headers=headers).json()["items"]]
    assert names == ["Alaska Dairy Distributor", "Puregold Wholesale"]
    found = client.get(URL, params={"q": "0917"}, headers=headers).json()
    assert [s["name"] for s in found["items"]] == ["Puregold Wholesale"]


def test_names_are_unique_per_store_ignoring_case(client, headers, other_headers):
    assert add(client, headers).status_code == 201
    duplicate = add(client, headers, name="  PUREGOLD wholesale ")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["fields"] == {"name": "Already exists"}
    assert add(client, other_headers).status_code == 201  # another store may use the name


def test_update_and_archive(client, headers):
    supplier = add(client, headers).json()
    url = f"{URL}/{supplier['id']}"

    updated = client.patch(url, json={"phone": "02 8123 4567", "notes": None}, headers=headers)
    assert updated.json()["phone"] == "02 8123 4567"
    assert updated.json()["name"] == "Puregold Wholesale"  # untouched fields stay

    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(URL, headers=headers).json()["total"] == 0
    archived = client.get(URL, params={"include_archived": True}, headers=headers).json()
    assert archived["items"][0]["is_active"] is False


def test_invalid_email_is_a_field_error(client, headers):
    response = add(client, headers, email="not-an-email")
    assert response.status_code == 422
    assert "email" in response.json()["error"]["fields"]


def test_cashiers_cannot_see_or_change_suppliers(client, org, headers):
    supplier = add(client, headers).json()
    cashier = auth_headers(org, Role.CASHIER)
    assert client.get(URL, headers=cashier).status_code == 403
    assert client.get(f"{URL}/{supplier['id']}", headers=cashier).status_code == 403
    assert add(client, cashier, name="Other").status_code == 403


def test_managers_can_manage_suppliers(client, org):
    manager = auth_headers(org, Role.MANAGER)
    assert add(client, manager).status_code == 201


def test_other_stores_suppliers_are_not_found(client, headers, other_headers):
    theirs = add(client, other_headers).json()
    assert client.get(f"{URL}/{theirs['id']}", headers=headers).status_code == 404
    assert client.patch(f"{URL}/{theirs['id']}", json={}, headers=headers).status_code == 404
