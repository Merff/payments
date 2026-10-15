from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.broker import broker
from app.models import Outbox
from app.outbox import publish_outbox


# Событие из outbox публикуется один раз и помечается опубликованным
async def test_publish_outbox(session: AsyncSession):
    message = Outbox(queue="payments.new", payload={"payment_id": 1})
    session.add(message)
    await session.commit()

    with patch.object(broker, "publish") as publish:
        await publish_outbox(session)
        await publish_outbox(session)

    publish.assert_called_once_with({"payment_id": 1}, queue="payments.new", persist=True)
    assert message.published_at is not None
