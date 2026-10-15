from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB", "USD", "EUR"]
    description: str = Field(max_length=255)
    meta: dict[str, Any] = {}
    webhook_url: str | None = Field(None, max_length=255)


class PaymentAccepted(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: int = Field(validation_alias="id")
    status: str
    created_at: datetime


class PaymentRead(PaymentAccepted):
    amount: Decimal
    currency: str
    description: str
    meta: dict[str, Any]
    webhook_url: str | None
    processed_at: datetime | None


class PaymentEvent(BaseModel):
    payment_id: int
