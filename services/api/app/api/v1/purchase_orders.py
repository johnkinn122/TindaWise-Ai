import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.api.deps import CanApprovePurchases, CanManageInventory, DbSession
from app.schemas.common import Page
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderStatusName,
    PurchaseOrderSummary,
    PurchaseOrderUpdate,
    ReceiveInput,
)
from app.services import purchase_orders as service

# Owners and managers draft, edit and receive; only the owner approves (see /approve).
router = APIRouter(prefix="/purchase-orders", tags=["purchase orders"])

IdempotencyKey = Annotated[
    str | None, Header(max_length=80, description="Same key when retrying the same request")
]
REPLAYED = {200: {"description": "Replayed request: the original result is returned"}}


def _key(value: str | None) -> str | None:
    # A blank header means "no key", never a key of "" shared by every request.
    return (value.strip() or None) if value else None


@router.get("", response_model=Page[PurchaseOrderSummary])
def list_purchase_orders(
    db: DbSession,
    auth: CanManageInventory,
    status_: Annotated[list[PurchaseOrderStatusName] | None, Query(alias="status")] = None,
    supplier_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = service.list_purchase_orders(
        db,
        auth.organization.id,
        statuses=list(status_) if status_ else None,
        supplier_id=supplier_id,
        limit=limit,
        offset=offset,
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED, responses=REPLAYED
)
def create_purchase_order(
    data: PurchaseOrderCreate,
    db: DbSession,
    auth: CanManageInventory,
    response: Response,
    idempotency_key: IdempotencyKey = None,
):
    """Creates a draft. Unit costs default to each product's current cost."""
    po, created = service.create_purchase_order(
        db,
        org_id=auth.organization.id,
        data=data,
        user_id=auth.user.id,
        idempotency_key=_key(idempotency_key),
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return service.to_read(db, po)


@router.post(
    "/from-reorder",
    response_model=PurchaseOrderRead,
    status_code=status.HTTP_201_CREATED,
    responses=REPLAYED,
)
def create_from_reorder(
    db: DbSession,
    auth: CanManageInventory,
    response: Response,
    idempotency_key: IdempotencyKey = None,
):
    """A draft holding the Overview's current reorder suggestions. Pick the supplier, review,
    then ask the owner to approve."""
    po, created = service.create_from_reorder(
        db, org_id=auth.organization.id, user_id=auth.user.id, idempotency_key=_key(idempotency_key)
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return service.to_read(db, po)


@router.get("/{po_id}", response_model=PurchaseOrderRead)
def get_purchase_order(po_id: uuid.UUID, db: DbSession, auth: CanManageInventory):
    return service.to_read(db, service.get_purchase_order(db, auth.organization.id, po_id))


@router.patch("/{po_id}", response_model=PurchaseOrderRead)
def update_draft(
    po_id: uuid.UUID, data: PurchaseOrderUpdate, db: DbSession, auth: CanManageInventory
):
    return service.to_read(db, service.update_draft(db, auth.organization.id, po_id, data))


@router.post("/{po_id}/approve", response_model=PurchaseOrderRead)
def approve(po_id: uuid.UUID, db: DbSession, auth: CanApprovePurchases):
    return service.to_read(db, service.approve(db, auth.organization.id, po_id, auth.user.id))


@router.post(
    "/{po_id}/receive",
    response_model=PurchaseOrderRead,
    status_code=status.HTTP_201_CREATED,
    responses=REPLAYED,
)
def receive(
    po_id: uuid.UUID,
    data: ReceiveInput,
    db: DbSession,
    auth: CanManageInventory,
    response: Response,
    idempotency_key: IdempotencyKey = None,
):
    """Records one delivery: adds stock and updates each product's cost to the order's cost."""
    po, created = service.receive(
        db,
        org_id=auth.organization.id,
        po_id=po_id,
        data=data,
        user_id=auth.user.id,
        idempotency_key=_key(idempotency_key),
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return service.to_read(db, po)


@router.post("/{po_id}/close", response_model=PurchaseOrderRead)
def close_short(po_id: uuid.UUID, db: DbSession, auth: CanManageInventory):
    return service.to_read(db, service.close_short(db, auth.organization.id, po_id, auth.user.id))


@router.post("/{po_id}/cancel", response_model=PurchaseOrderRead)
def cancel(po_id: uuid.UUID, db: DbSession, auth: CanManageInventory):
    po = service.cancel(db, auth.organization.id, po_id, auth.user.id, auth.role)
    return service.to_read(db, po)
