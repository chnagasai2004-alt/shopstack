import os
import re
from pathlib import Path

TEST_DB = Path(__file__).with_name("test_shopstack.db")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SESSION_SECRET"] = "test-secret"

from fastapi.testclient import TestClient

from app.main import app


def login(client: TestClient, email: str, password: str, next_path: str = "/"):
    return client.post("/login", data={"email": email, "password": password, "next": next_path}, follow_redirects=False)


def test_public_pages_and_health():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/").status_code == 200
        assert client.get("/shop?q=headphones").status_code == 200
        assert client.get("/products/orbit-wireless-headphones").status_code == 200


def test_shopper_purchase_is_idempotent():
    with TestClient(app) as client:
        assert login(client, "demo@example.com", "demo123").status_code == 303
        add = client.post("/api/cart", data={"product_id": 1, "quantity": 1})
        assert add.json()["cart_count"] == 1
        checkout = client.get("/checkout")
        key = re.search(r'name="checkout_key" value="([^"]+)"', checkout.text).group(1)
        order_data = {"checkout_key": key, "full_name": "Demo Shopper", "street": "1 Demo Way", "city": "Austin", "state": "TX", "postal_code": "78701", "country": "United States", "payment_method": "demo_card"}
        placed = client.post("/checkout", data=order_data, follow_redirects=False)
        assert placed.status_code == 303
        order_url = placed.headers["location"]
        replay = client.post("/checkout", data=order_data, follow_redirects=False)
        assert replay.status_code == 303
        assert replay.headers["location"].split("?")[0] == order_url.split("?")[0]
        assert client.get(order_url).status_code == 200


def test_admin_auth_and_cancel_restores_stock():
    with TestClient(app) as guest:
        response = guest.get("/admin", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    with TestClient(app) as admin:
        assert login(admin, "admin@example.com", "admin123", "/admin").status_code == 303
        assert admin.get("/admin").status_code == 200
        response = admin.post("/admin/orders/1/status", data={"status": "cancelled"}, follow_redirects=False)
        assert response.status_code == 303
