from locust import HttpUser, task, between, events
import uuid
import httpx
import time

USERS = [{"email": f"load_{i}@test.com", "password": "password123"} for i in range(50)]

# @events.test_start.add_listener
# def setup_users(environment, **kwargs):
#     """Pre-register all test users before load test begins."""
#     for user in USERS:
#         try:
#             httpx.post(f"{environment.host}/auth/register", json=user, timeout=30)
#             time.sleep(0.1)
#         except:
#             pass  # already exists, fine

SESSIONS = {}

@events.test_start.add_listener
def setup_sessions(environment, **kwargs):
    """Pre-login all users before load test begins."""
    import time
    for user in USERS:
        try:
            response = httpx.post(
                f"{environment.host}/auth/login", 
                json=user, 
                timeout=30
            )
            if response.status_code == 200:
                SESSIONS[user["email"]] = response.json()["session_id"]
            time.sleep(0.2)  # stagger bcrypt operations
        except:
            pass

class BullpenUser(HttpUser):
    wait_time = between(1, 3)
    def on_start(self):
        import random
        email = random.choice(list(SESSIONS.keys()))
        self.session_id = SESSIONS[email]
        self.headers = {"X-Session-Id": self.session_id}

    @task(10)
    def get_price(self):
        if not self.session_id:
            return
        self.client.get("/prices/AAPL", headers=self.headers)

    @task(3)
    def get_portfolio(self):
        if not self.session_id:
            return
        self.client.get("/portfolio/me", headers=self.headers)

    @task(1)
    def submit_trade(self):
        if not self.session_id:
            return
        self.client.post("/trades", json={
            "symbol": "AAPL",
            "quantity": 1,
            "direction": "buy",
            "price": 333.02
        }, headers=self.headers)