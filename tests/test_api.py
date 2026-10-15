from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Outbox, Payment

URL = "/api/v1/payments"
PAYLOAD = {
    "amount": "100.50",
    "currency": "RUB",
    "description": "Order #1",
    "meta": {"order_id": 1},
    "webhook_url": "http://example.com/webhook",
}


async def test_create_payment(client: AsyncClient, session: AsyncSession):
    response = await client.post(URL, json=PAYLOAD, headers={"Idempotency-Key": "key-1"})

    assert response.status_code == 202
    assert response.json().keys() == {"payment_id", "status", "created_at"}
    assert response.json()["status"] == "pending"

    outbox = await session.scalar(select(Outbox))
    assert (outbox.queue, outbox.payload) == ("payments.new", {"payment_id": response.json()["payment_id"]})


async def test_create_payment_with_used_idempotency_key(client: AsyncClient, session: AsyncSession):
    await client.post(URL, json=PAYLOAD, headers={"Idempotency-Key": "key-1"})
    response = await client.post(URL, json=PAYLOAD, headers={"Idempotency-Key": "key-1"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["header", "idempotency-key"]
    assert await session.scalar(select(func.count()).select_from(Payment)) == 1


async def test_create_payment_with_invalid_payload(client: AsyncClient):
    response = await client.post(URL, json=PAYLOAD | {"amount": "-1"}, headers={"Idempotency-Key": "key-1"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "amount"]


async def test_create_payment_requires_idempotency_key(client: AsyncClient):
    response = await client.post(URL, json=PAYLOAD)

    assert response.status_code == 422


async def test_get_payment(client: AsyncClient):
    created = await client.post(URL, json=PAYLOAD, headers={"Idempotency-Key": "key-1"})
    payment_id = created.json()["payment_id"]

    response = await client.get(f"{URL}/{payment_id}")

    assert response.status_code == 200
    assert response.json() | PAYLOAD == response.json()


async def test_get_missing_payment(client: AsyncClient):
    response = await client.get(f"{URL}/1")

    assert response.status_code == 404


async def test_invalid_api_key(client: AsyncClient):
    response = await client.get(f"{URL}/1", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401
