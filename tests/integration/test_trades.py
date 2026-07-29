import httpx
import pytest

BASE_URL = "http://localhost:8000"


import httpx
import pytest
import uuid

BASE_URL = "http://localhost:8000"

@pytest.mark.asyncio
async def test_submit_valid_trade():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Register and login to get session
        email = f"trade_test_{uuid.uuid4()}@test.com"
        register = await client.post("/auth/register", json={
            "email": email,
            "password": "password123"
        })
        session_id = register.json()["session_id"]

        # Submit trade with session header
        response = await client.post("/trades", json={
            "symbol": "AAPL",
            "quantity": 10,
            "direction": "buy",
            "price": 333.01
        }, headers={"X-Session-Id": session_id})

        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        assert "trade_id" in response.json()


@pytest.mark.asyncio
async def test_submit_invalid_direction():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Register and login to get session
        email = f"trade_test_{uuid.uuid4()}@test.com"
        register = await client.post("/auth/register", json={
            "email": email,
            "password": "password123"
        })
        session_id = register.json()["session_id"]

        # Submit trade with session header
        response = await client.post("/trades", json={
            "symbol": "AAPL",
            "quantity": 10,
            "direction": "hold",
            "price": 333.01
        }, headers={"X-Session-Id": session_id})

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_unauthenticated():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.post("/trades", json={
            "symbol": "AAPL",
            "quantity": 10,
            "direction": "buy",
            "price": 333.01
        })
        assert response.status_code == 422