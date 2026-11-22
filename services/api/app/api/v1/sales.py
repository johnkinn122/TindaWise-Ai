import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.api.deps import Auth, CanManageInventory, DbSession
from app.core.errors import InvalidInputError, NotFoundError
from app.models import Role, Sale
from app.schemas.common import Page
from app.schemas.sale import RefundCreate, RefundRead, SaleCreate, SaleRead, SaleSummary
from app.services import refunds as refund_service
from app.services import sales as service

router = APIRouter(prefix="/sales", tags=["sales"])


def _read(db: DbSession, sale: Sale) -> SaleRead:
    names = service.cashier_names(
        db, {sale.created_by_user_id} | {r.created_by_user_id for r in sale.refunds}
    )
    refunds = [
        RefundRead.model_validate(r).model_copy(
            update={"refunded_by_name": names.get(r.created_by_user_id)}
        )
        for r in sale.refunds
    ]
    return SaleRead.model_validate(sale).model_copy(
        update={"cashier_name": names.get(sale.created_by_user_id), "refunds": refunds}
    )


def _receipt_number(value: str | None) -> int | None:
    """Accepts "S-000123", "000123" or "123"."""
    if value is None or not value.strip():
        return None
    match = re.fullmatch(r"\s*(?:S-?)?0*(\d{1,9})\s*", value, flags=re.IGNORECASE)
    if match is None:
        raise InvalidInputError(
            "Enter a receipt number like S-000123 or 123.",
            fields={"receipt": "Not a receipt number"},
        )
    return int(match.group(1))


@router.post(
    "",
    response_model=SaleRead,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Replayed checkout: the original sale is returned"}},
)
def create_sale(
    data: SaleCreate,
    db: DbSession,
    auth: Auth,  # every role can sell, cashiers included
    response: Response,
    idempotency_key: Annotated[
        str | None, Header(max_length=80, description="Same key when retrying the same checkout")
    ] = None,
):
    key = idempotency_key.strip() if idempotency_key else None
    sale, created = service.create_sale(
        db,
        org_id=auth.organization.id,
        data=data,
        cashier_id=auth.user.id,
        idempotency_key=key or None,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return _read(db, sale)


@router.get("", response_model=Page[SaleSummary])
def list_sales(
    db: DbSession,
    auth: Auth,
    receipt: Annotated[
        str | None, Query(max_length=20, description="Receipt number: S-000123 or 123")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Owners and managers see every sale; cashiers see their own. Newest first."""
    only_mine = auth.role == Role.CASHIER
    rows, total = service.list_sales(
        db,
        auth.organization.id,
        cashier_id=auth.user.id if only_mine else None,
        receipt_number=_receipt_number(receipt),
        limit=limit,
        offset=offset,
    )
    names = service.cashier_names(db, {s.created_by_user_id for s in rows})
    items = [
        SaleSummary(
            id=s.id,
            receipt_number=s.receipt_number,
            total=s.total,
            refunded_total=s.refunded_total,
            payment_method=s.payment_method,
            created_at=s.created_at,
            cashier_name=names.get(s.created_by_user_id),
            item_count=sum(line.quantity for line in s.lines),
        )
        for s in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{sale_id}", response_model=SaleRead)
def get_sale(sale_id: uuid.UUID, db: DbSession, auth: Auth):
    sale = service.get_sale(db, auth.organization.id, sale_id)
    if auth.role == Role.CASHIER and sale.created_by_user_id != auth.user.id:
        # Same answer as "doesn't exist", so other cashiers' receipts aren't revealed.
        raise NotFoundError("Receipt not found.")
    return _read(db, sale)


@router.post(
    "/{sale_id}/refunds",
    response_model=SaleRead,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Replayed refund: the receipt is returned unchanged"}},
)
def create_refund(
    sale_id: uuid.UUID,
    data: RefundCreate,
    db: DbSession,
    auth: CanManageInventory,  # owners and managers only; cashiers can't give money back
    response: Response,
    idempotency_key: Annotated[
        str | None, Header(max_length=80, description="Same key when retrying the same refund")
    ] = None,
):
    """Refund some or all of the units on a receipt. Returns the receipt with all its refunds."""
    key = idempotency_key.strip() if idempotency_key else None
    sale, created = refund_service.create_refund(
        db,
        org_id=auth.organization.id,
        sale_id=sale_id,
        data=data,
        user_id=auth.user.id,
        idempotency_key=key or None,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return _read(db, sale)
