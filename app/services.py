from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import gateway
from app.broker import payments_queue
from app.models import Outbox, Payment, PaymentStatus
from app.schemas import PaymentCreate


class IdempotencyConflict(Exception):
    pass


async def create_payment(session: AsyncSession, data: PaymentCreate, idempotency_key: str) -> Payment:
    values = data.model_dump()
    payment = await session.scalar(
        insert(Payment)
        .values(**values, idempotency_key=idempotency_key)
        .on_conflict_do_nothing(index_elements=[Payment.idempotency_key])
        .returning(Payment)
    )
    if payment is None:
        payment = await session.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
        if any(getattr(payment, name) != value for name, value in values.items()):
            raise IdempotencyConflict
        return payment
    session.add(Outbox(queue=payments_queue.name, payload={"payment_id": payment.id}))
    await session.commit()
    return payment


async def process_payment(session: AsyncSession, payment_id: int) -> Payment | None:
    payment = await session.get(Payment, payment_id)
    await session.commit()
    if payment is None or payment.status != PaymentStatus.PENDING:
        return payment

    status = await gateway.charge(payment.amount, payment.currency, payment.idempotency_key)

    payment = await session.scalar(
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING)
        .values(status=status, processed_at=datetime.now(UTC).replace(tzinfo=None))
        .returning(Payment),
        execution_options={"populate_existing": True},
    ) or await session.get(Payment, payment_id, populate_existing=True)
    await session.commit()
    return payment


async def mark_webhook_sent(session: AsyncSession, payment: Payment) -> None:
    payment.webhook_sent_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
