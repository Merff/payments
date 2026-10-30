import asyncio
import random
from decimal import Decimal

from app.models import PaymentStatus


async def charge(amount: Decimal, currency: str, idempotency_key: str) -> PaymentStatus:
    await asyncio.sleep(random.uniform(2, 5))
    return PaymentStatus.SUCCEEDED if random.random() < 0.9 else PaymentStatus.FAILED
