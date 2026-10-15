from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB", "USD", "EUR"]
    description: str = Field(max_length=255)
    metadata: dict[str, Any] = {}
    webhook_url: str | None = Field(None, max_length=255)
