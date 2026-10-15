from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PlainSerializer


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB", "USD", "EUR"]
    description: str = Field(max_length=255)
    meta: dict[str, Any] = {}
    webhook_url: Annotated[HttpUrl, PlainSerializer(str)] | None = None


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
