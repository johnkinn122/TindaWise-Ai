import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.api.deps import Auth, DbSession
from app.core.errors import NotFoundError
from app.models import Role, Sale
from app.schemas.common import Page
from app.schemas.sale import SaleCreate, SaleRead, SaleSummary
from app.services import sales as service

router = APIRouter(prefix="/sales", tags=["sales"])


def _read(sale: Sale, names: dict[uuid.UUID, str]) -> SaleRead:
    return SaleRead.model_validate(sale).model_copy(
        update={"cashier_name": names.get(sale.created_by_user_id)}
    )


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
    return _read(sale, service.cashier_names(db, {sale.created_by_user_id}))


@router.get("", response_model=Page[SaleSummary])
def list_sales(
    db: DbSession,
    auth: Auth,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Owners and managers see every sale; cashiers see their own."""
    only_mine = auth.role == Role.CASHIER
    rows, total = service.list_sales(
        db,
        auth.organization.id,
        cashier_id=auth.user.id if only_mine else None,
        limit=limit,
        offset=offset,
    )
    names = service.cashier_names(db, {s.created_by_user_id for s in rows})
    items = [
        SaleSummary(
            id=s.id,
            receipt_number=s.receipt_number,
            total=s.total,
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
    return _read(sale, service.cashier_names(db, {sale.created_by_user_id}))
