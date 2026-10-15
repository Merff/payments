import asyncio

from faststream import FastStream

from app.broker import broker, payments_queue
from app.outbox import run_outbox_relay

app = FastStream(broker)


@app.after_startup
async def start_outbox_relay() -> None:
    await broker.declare_queue(payments_queue)
    relay = asyncio.create_task(run_outbox_relay())
    app.on_shutdown(relay.cancel)
