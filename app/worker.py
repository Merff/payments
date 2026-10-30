import asyncio
import logging
from typing import Any

import httpx
from faststream import FastStream
from faststream.rabbit import Channel
from faststream.rabbit.annotations import RabbitMessage

from app import services
from app.broker import broker, dead_letter_exchange, dead_letter_queue, payments_queue, retry_queues
from app.db import session_factory
from app.outbox import run_outbox_relay
from app.schemas import PaymentEvent, PaymentRead

logger = logging.getLogger(__name__)

app = FastStream(broker)


@app.on_startup
async def declare_queues() -> None:
    await broker.connect()
    queue = await broker.declare_queue(dead_letter_queue)
    await queue.bind(await broker.declare_exchange(dead_letter_exchange))
    for retry_queue in retry_queues:
        await broker.declare_queue(retry_queue)


@app.after_startup
async def start_outbox_relay() -> None:
    relay = asyncio.create_task(run_outbox_relay())
    app.on_shutdown(relay.cancel)


@broker.subscriber(payments_queue, channel=Channel(prefetch_count=10))
async def handle_payment(event: PaymentEvent, message: RabbitMessage) -> None:
    try:
        async with session_factory() as session:
            payment = await services.process_payment(session, event.payment_id)
            if payment and payment.webhook_url and payment.webhook_sent_at is None:
                await send_webhook(payment.webhook_url, PaymentRead.model_validate(payment).model_dump(mode="json"))
                await services.mark_webhook_sent(session, payment)
    except Exception:
        retries = message.headers.get("x-retries", 0)
        if retries >= len(retry_queues):
            raise
        logger.warning("Payment %s processing failed, retry %s", event.payment_id, retries + 1, exc_info=True)
        try:
            await broker.publish(
                event.model_dump(), queue=retry_queues[retries], headers={"x-retries": retries + 1}, persist=True
            )
        except Exception:
            logger.exception("Payment %s retry publishing failed, requeue", event.payment_id)
            await message.nack(requeue=True)


async def send_webhook(url: str, payload: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=3) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
