import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker import broker
from app.db import session_factory
from app.models import Outbox

logger = logging.getLogger(__name__)


async def publish_outbox(session: AsyncSession, limit: int = 100) -> None:
    messages = await session.scalars(
        select(Outbox)
        .where(Outbox.published_at.is_(None))
        .order_by(Outbox.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    for message in messages:
        await broker.publish(message.payload, queue=message.queue, persist=True)
        message.published_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()


async def run_outbox_relay(interval: float = 1) -> None:
    while True:
        try:
            async with session_factory() as session:
                await publish_outbox(session)
        except Exception:
            logger.exception("Outbox publishing failed")
        await asyncio.sleep(interval)
