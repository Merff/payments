import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.security import APIKeyHeader
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionDep
from app.models import Payment
from app.schemas import PaymentAccepted, PaymentCreate, PaymentRead


def verify_api_key(api_key: Annotated[str, Security(APIKeyHeader(name="X-API-Key"))]) -> None:
    if not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")


router = APIRouter(prefix="/api/v1/payments", tags=["payments"], dependencies=[Depends(verify_api_key)])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAccepted)
async def create_payment(
    data: PaymentCreate,
    idempotency_key: Annotated[str, Header(max_length=255)],
    session: SessionDep,
) -> Payment:
    payment = await session.scalar(
        insert(Payment)
        .values(**data.model_dump(), idempotency_key=idempotency_key)
        .on_conflict_do_nothing(index_elements=[Payment.idempotency_key])
        .returning(Payment)
    )
    if payment is None:
        raise RequestValidationError(
            [{"type": "duplicate", "loc": ("header", "idempotency-key"), "msg": "Idempotency key already used"}]
        )
    await session.commit()
    return payment


@router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment(payment_id: int, session: SessionDep) -> Payment:
    if payment := await session.get(Payment, payment_id):
        return payment
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
