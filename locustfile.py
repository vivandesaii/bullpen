from locust import HttpUser, task, between, events
import uuid
import httpx
import time

USERS = [{"email": f"load_{i}@test.com", "password": "password123"} for i in range(50)]

@events.test_start.add_listener
def setup_users(environment, **kwargs):
    """Pre-register all test users before load test begins."""
    for user in USERS:
        try:
            httpx.post(f"{environment.host}/auth/register", json=user, timeout=30)
            time.sleep(0.1)
        except:
            pass  # already exists, fine

class BullpenUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        import random
        creds = random.choice(USERS)
        response = self.client.post("/auth/login", json=creds)
        self.session_id = response.json().get("session_id")
        self.headers = {"X-Session-Id": self.session_id}

    @task(10)
    def get_price(self):
        self.client.get("/prices/AAPL", headers=self.headers)

    @task(3)
    def get_portfolio(self):
        self.client.get("/portfolio/me", headers=self.headers)

    @task(1)
    def submit_trade(self):
        self.client.post("/trades", json={
            "symbol": "AAPL",
            "quantity": 1,
            "direction": "buy",
            "price": 333.02
        }, headers=self.headers)