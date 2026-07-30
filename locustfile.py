from locust import HttpUser, task, between
import uuid

class BullpenUser(HttpUser):
    wait_time = between(1, 3)  # wait 1-3 seconds between tasks
    
    def on_start(self):
        """Runs once when each simulated user starts — register and login."""
        email = f"load_test_{uuid.uuid4()}@test.com"
        response = self.client.post("/auth/register", json={
            "email": email,
            "password": "password123"
        })
        self.session_id = response.json()["session_id"]
        self.headers = {"X-Session-Id": self.session_id}

    @task(10)  # weight 10 — runs 10x more than weight 1 tasks
    def get_price(self):
        """Hit price endpoint — this is where Redis cache shines."""
        self.client.get("/prices/AAPL", headers=self.headers)

    @task(3)
    def get_portfolio(self):
        """Check portfolio — hits Redis cache after first request."""
        self.client.get("/portfolio/me", headers=self.headers)

    @task(1)
    def submit_trade(self):
        """Submit a trade — goes through SQS pipeline."""
        self.client.post("/trades", json={
            "symbol": "AAPL",
            "quantity": 1,
            "direction": "buy",
            "price": 333.02
        }, headers=self.headers)