import httpx
import pytest
import uuid

email = f"test_{uuid.uuid4()}@test.com"
BASE_URL = "http://localhost:8000"

@pytest.mark.asyncio
async def test_register_new_user():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.post("/auth/register", json={
            "email": email,
            "password": "password123"
        })
        assert response.status_code == 200
        assert "session_id" in response.json()

@pytest.mark.asyncio
async def test_login_valid_user():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Register first
        await client.post("/auth/register", json={
            "email": email,
            "password": "password123"
        })

        # Then login
        response = await client.post("/auth/login", json={
            "email": email,
            "password": "password123"
        })

        assert response.status_code == 200
        assert "session_id" in response.json()


@pytest.mark.asyncio  
async def test_login_invalid_password():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
            # Register first
            await client.post("/auth/register", json={
                "email": email,
                "password": "password123"
            })
    
            # Then login
            response = await client.post("/auth/login", json={
                "email": email,
                "password": "password"
            })
    
            assert response.status_code == 401
