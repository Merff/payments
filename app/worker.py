import asyncio
import random
from datetime import UTC, datetime
from typing import Any

import httpx
from faststream import FastStream
from faststream.rabbit import Channel

from app.broker import broker, dead_letter_exchange, dead_letter_queue, payments_queue
from app.db import session_factory
from app.models import Payment, PaymentStatus
from app.outbox import run_outbox_relay
from app.schemas import PaymentEvent, PaymentRead

app = FastStream(broker)


@app.on_startup
async def declare_dead_letter_queue() -> None:
    await broker.connect()
    queue = await broker.declare_queue(dead_letter_queue)
    await queue.bind(await broker.declare_exchange(dead_letter_exchange))


@app.after_startup
async def start_outbox_relay() -> None:
    relay = asyncio.create_task(run_outbox_relay())
    app.on_shutdown(relay.cancel)


@broker.subscriber(payments_queue, channel=Channel(prefetch_count=10))
async def process_payment(event: PaymentEvent) -> None:
    async with session_factory() as session:
        payment = await session.get(Payment, event.payment_id, with_for_update=True)
        if payment is None:
            return
        if payment.status == PaymentStatus.PENDING:
            await asyncio.sleep(random.uniform(2, 5))
            payment.status = PaymentStatus.SUCCEEDED if random.random() < 0.9 else PaymentStatus.FAILED
            payment.processed_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()

        if payment.webhook_url and payment.webhook_sent_at is None:
            await send_webhook(payment.webhook_url, PaymentRead.model_validate(payment).model_dump(mode="json"))
            payment.webhook_sent_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()


async def send_webhook(url: str, payload: dict[str, Any], attempts: int = 3) -> None:
    async with httpx.AsyncClient(timeout=3) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return
            except httpx.HTTPError:
                if attempt == attempts - 1:
                    raise
                await asyncio.sleep(2**attempt)
