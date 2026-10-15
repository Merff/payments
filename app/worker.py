import asyncio
import random
from datetime import UTC, datetime

import httpx
from faststream import FastStream

from app.broker import broker, payments_queue
from app.db import session_factory
from app.models import Payment
from app.outbox import run_outbox_relay
from app.schemas import PaymentEvent, PaymentRead

app = FastStream(broker)


@app.after_startup
async def start_outbox_relay() -> None:
    relay = asyncio.create_task(run_outbox_relay())
    app.on_shutdown(relay.cancel)


@broker.subscriber(payments_queue)
async def process_payment(event: PaymentEvent) -> None:
    async with session_factory() as session:
        payment = await session.get(Payment, event.payment_id, with_for_update=True)
        if payment is None or payment.status != "pending":
            return
        await asyncio.sleep(random.uniform(2, 5))
        payment.status = "succeeded" if random.random() < 0.9 else "failed"
        payment.processed_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()

    if payment.webhook_url:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(
                payment.webhook_url, json=PaymentRead.model_validate(payment).model_dump(mode="json")
            )
            response.raise_for_status()
