from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str]
    description: Mapped[str]
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    status: Mapped[str] = mapped_column(default="pending")
    idempotency_key: Mapped[str] = mapped_column(unique=True)
    webhook_url: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.timezone("utc", func.now()))
    processed_at: Mapped[datetime | None]
