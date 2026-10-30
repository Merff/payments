from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from faststream.rabbit import TestRabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker import payments_queue, retry_queues
from app.models import Payment, PaymentStatus
from app.worker import broker


async def create_payment(session: AsyncSession, **values) -> Payment:
    payment = Payment(
        amount=Decimal("100.50"),
        currency="RUB",
        description="Order #1",
        idempotency_key="key-1",
        webhook_url="http://example.com/webhook",
        **values,
    )
    session.add(payment)
    await session.commit()
    return payment


@pytest.fixture(autouse=True)
def webhook():
    response = httpx.Response(200, request=httpx.Request("POST", "http://example.com/webhook"))
    with patch("httpx.AsyncClient.post", return_value=response) as post:
        yield post


# Consumer обновляет статус платежа результатом шлюза и отправляет вебхук
@pytest.mark.parametrize("status", [PaymentStatus.SUCCEEDED, PaymentStatus.FAILED])
async def test_process_payment(session: AsyncSession, webhook, status: PaymentStatus):
    payment = await create_payment(session)

    with patch("app.gateway.charge", return_value=status) as charge:
        async with TestRabbitBroker(broker) as test_broker:
            await test_broker.publish({"payment_id": payment.id}, queue=payments_queue)

    charge.assert_called_once_with(Decimal("100.50"), "RUB", "key-1")
    await session.refresh(payment)
    assert payment.status == status
    assert payment.processed_at is not None
    assert payment.webhook_sent_at is not None
    webhook.assert_called_once()
    assert webhook.call_args.args == ("http://example.com/webhook",)
    assert webhook.call_args.kwargs["json"]["status"] == status


# Уже обработанный платёж с отправленным вебхуком пропускается
async def test_process_payment_skips_processed(session: AsyncSession, webhook):
    payment = await create_payment(session, status=PaymentStatus.SUCCEEDED, webhook_sent_at=datetime(2026, 1, 1))

    async with TestRabbitBroker(broker) as test_broker:
        await test_broker.publish({"payment_id": payment.id}, queue=payments_queue)

    webhook.assert_not_called()


# При повторной доставке обработанного платежа без вебхука шлюз не вызывается, а вебхук досылается
async def test_process_payment_resends_webhook(session: AsyncSession, webhook):
    payment = await create_payment(session, status=PaymentStatus.FAILED)

    with patch("app.gateway.charge") as charge:
        async with TestRabbitBroker(broker) as test_broker:
            await test_broker.publish({"payment_id": payment.id}, queue=payments_queue)

    await session.refresh(payment)
    charge.assert_not_called()
    assert payment.webhook_sent_at is not None
    webhook.assert_called_once()
    assert webhook.call_args.kwargs["json"]["status"] == "failed"


# При ошибке сообщение уходит в очередь повторов следующего уровня
@pytest.mark.parametrize("retries", [0, 1])
async def test_process_payment_retries(session: AsyncSession, webhook, retries: int):
    payment = await create_payment(session, status=PaymentStatus.SUCCEEDED)
    webhook.side_effect = httpx.ConnectError("Connection refused")

    async with TestRabbitBroker(broker) as test_broker:
        publish = test_broker.publish
        with patch.object(broker, "publish") as retry:
            await publish({"payment_id": payment.id}, queue=payments_queue, headers={"x-retries": retries})

    retry.assert_called_once_with(
        {"payment_id": payment.id}, queue=retry_queues[retries], headers={"x-retries": retries + 1}, persist=True
    )


# После последней попытки ошибка пробрасывается, и сообщение уходит в DLQ
async def test_process_payment_fails_after_retries(session: AsyncSession, webhook):
    payment = await create_payment(session, status=PaymentStatus.SUCCEEDED)
    webhook.side_effect = httpx.ConnectError("Connection refused")

    async with TestRabbitBroker(broker) as test_broker:
        with pytest.raises(httpx.ConnectError):
            await test_broker.publish(
                {"payment_id": payment.id}, queue=payments_queue, headers={"x-retries": len(retry_queues)}
            )
