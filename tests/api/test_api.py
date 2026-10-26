import bcrypt
import pytest
from fastapi.testclient import TestClient

from pricewatch.api.config import ApiSettings, get_api_settings
from pricewatch.api.deps import get_recommender, get_repository
from pricewatch.api.main import app

KEY = "0" * 32
SETTINGS = ApiSettings(
    jwt_secret="test-secret-that-is-long-enough-for-hs256",
    api_analyst_password_hash=bcrypt.hashpw(b"analyst123", bcrypt.gensalt(4)).decode(),
    api_admin_password_hash=bcrypt.hashpw(b"admin123", bcrypt.gensalt(4)).decode(),
)
PRODUCT = {
    "product_master_key": KEY,
    "canonical_name": "Rinso Anti Noda 770g",
    "brand": "Rinso",
    "category": "Laundry",
    "size_value": 770,
    "size_unit": "g",
    "pack_qty": 1,
    "n_platforms_listed": 3,
    "data_origins": "sample",
    "match_method": "rule_key",
}


class FakeRepository:
    def __init__(self):
        self.calls = {}

    def list_products(self, *args):
        self.calls["list_products"] = args
        return [PRODUCT], 41

    def get_product(self, key):
        return {**PRODUCT, "listings": []} if key == KEY else None

    def list_prices(self, *args):
        self.calls["list_prices"] = args
        return [], 0

    def latest_run_id(self):
        return "11111111-2222-3333-4444-555555555555"

    def list_recommendations(self, *args):
        self.calls["list_recommendations"] = args
        return [], 0


@pytest.fixture
def repo():
    return FakeRepository()


@pytest.fixture
def client(repo):
    app.dependency_overrides[get_api_settings] = lambda: SETTINGS
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_recommender] = lambda: (
        lambda: {"run_id": "r1", "model_version": "v", "run_at": "t", "rows": 3, "reasons": {}}
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def token(client, user, password):
    response = client.post("/auth/token", data={"username": user, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_request_without_token_is_rejected_with_401(client):
    assert client.get("/products").status_code == 401


def test_wrong_password_gets_no_token(client):
    response = client.post("/auth/token", data={"username": "admin", "password": "nope"})
    assert response.status_code == 401


def test_tampered_token_is_rejected(client):
    headers = token(client, "analyst", "analyst123")
    headers["Authorization"] = headers["Authorization"][:-3] + "abc"
    assert client.get("/products", headers=headers).status_code == 401


def test_analyst_can_read_products_with_pagination_envelope(client):
    response = client.get(
        "/products?page=2&page_size=5", headers=token(client, "analyst", "analyst123")
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["page"], body["page_size"], body["total"]) == (2, 5, 41)
    assert body["items"][0]["brand"] == "Rinso"


def test_filters_reach_the_repository(client, repo):
    client.get(
        "/products?brand=Rinso&q=noda&data_origin=sample",
        headers=token(client, "analyst", "analyst123"),
    )
    assert repo.calls["list_products"] == ("Rinso", None, "noda", "sample", 1, 20)


def test_analyst_cannot_trigger_a_recommendation_run(client):
    response = client.post("/recommendations/runs", headers=token(client, "analyst", "analyst123"))
    assert response.status_code == 403


def test_admin_can_trigger_a_recommendation_run(client):
    response = client.post("/recommendations/runs", headers=token(client, "admin", "admin123"))
    assert response.status_code == 201
    assert response.json()["rows"] == 3


def test_page_size_above_100_is_rejected(client):
    headers = token(client, "analyst", "analyst123")
    assert client.get("/prices?page_size=101", headers=headers).status_code == 422


def test_page_zero_is_rejected(client):
    headers = token(client, "analyst", "analyst123")
    assert client.get("/prices?page=0", headers=headers).status_code == 422


def test_date_from_after_date_to_is_rejected(client):
    headers = token(client, "analyst", "analyst123")
    response = client.get("/prices?date_from=2026-10-10&date_to=2026-10-01", headers=headers)
    assert response.status_code == 422


def test_unknown_platform_is_rejected(client):
    headers = token(client, "analyst", "analyst123")
    assert client.get("/prices?platform=shopee", headers=headers).status_code == 422


def test_unknown_product_is_404_and_malformed_key_is_422(client):
    headers = token(client, "analyst", "analyst123")
    assert client.get("/products/" + "f" * 32, headers=headers).status_code == 404
    assert client.get("/products/not-a-key", headers=headers).status_code == 422


def test_recommendations_default_to_the_latest_run(client, repo):
    client.get("/recommendations", headers=token(client, "analyst", "analyst123"))
    assert repo.calls["list_recommendations"][2] == "11111111-2222-3333-4444-555555555555"


def test_openapi_documents_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/auth/token",
        "/health",
        "/products",
        "/products/{product_master_key}",
        "/prices",
        "/recommendations",
        "/recommendations/runs",
    } <= set(paths)
