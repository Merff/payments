from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from faststream.rabbit import TestRabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker import payments_queue
from app.models import Payment
from app.worker import broker, send_webhook


async def create_payment(session: AsyncSession, **values) -> Payment:
    payment = Payment(
        amount=Decimal("100.50"), currency="RUB", description="Order #1", idempotency_key="key-1", **values
    )
    session.add(payment)
    await session.commit()
    return payment


@pytest.fixture(autouse=True)
def webhook():
    response = httpx.Response(200, request=httpx.Request("POST", "http://example.com/webhook"))
    with patch("httpx.AsyncClient.post", return_value=response) as post:
        yield post


# Consumer обновляет статус платежа и отправляет вебхук
@pytest.mark.parametrize(("chance", "status"), [(0.5, "succeeded"), (0.95, "failed")])
async def test_process_payment(session: AsyncSession, webhook, chance: float, status: str):
    payment = await create_payment(session, webhook_url="http://example.com/webhook")

    with patch("random.uniform", return_value=0), patch("random.random", return_value=chance):
        async with TestRabbitBroker(broker) as test_broker:
            await test_broker.publish({"payment_id": payment.id}, queue=payments_queue)

    await session.refresh(payment)
    assert payment.status == status
    assert payment.processed_at is not None
    assert payment.webhook_sent_at is not None

    webhook.assert_called_once()
    assert webhook.call_args.args == ("http://example.com/webhook",)
    assert webhook.call_args.kwargs["json"]["status"] == status


# Уже обработанный платёж с отправленным вебхуком пропускается
async def test_process_payment_skips_processed(session: AsyncSession, webhook):
    payment = await create_payment(
        session, status="succeeded", webhook_url="http://example.com/webhook", webhook_sent_at=datetime(2026, 1, 1)
    )

    async with TestRabbitBroker(broker) as test_broker:
        await test_broker.publish({"payment_id": payment.id}, queue=payments_queue)

    webhook.assert_not_called()


# При повторной доставке обработанного платежа без вебхука досылается только вебхук
async def test_process_payment_resends_webhook(session: AsyncSession, webhook):
    payment = await create_payment(session, status="failed", webhook_url="http://example.com/webhook")

    async with TestRabbitBroker(broker) as test_broker:
        await test_broker.publish({"payment_id": payment.id}, queue=payments_queue)

    await session.refresh(payment)
    assert payment.status == "failed"
    assert payment.webhook_sent_at is not None
    assert webhook.call_args.kwargs["json"]["status"] == "failed"


# Вебхук доходит с третьей попытки с паузами 1 и 2 секунды
async def test_webhook_retries():
    error = httpx.ConnectError("Connection refused")
    response = httpx.Response(200, request=httpx.Request("POST", "http://example.com/webhook"))

    with (
        patch("httpx.AsyncClient.post", side_effect=[error, error, response]) as post,
        patch("asyncio.sleep") as sleep,
    ):
        await send_webhook("http://example.com/webhook", {})

    assert post.call_count == 3
    assert [call.args for call in sleep.call_args_list] == [(1,), (2,)]


# После трёх неудачных попыток ошибка пробрасывается
async def test_webhook_fails_after_retries():
    with (
        patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")) as post,
        patch("asyncio.sleep"),
        pytest.raises(httpx.ConnectError),
    ):
        await send_webhook("http://example.com/webhook", {})

    assert post.call_count == 3
