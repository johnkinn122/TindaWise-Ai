import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.api.deps import CanManageInventory, CurrentOrg, DbSession
from app.schemas.common import Page
from app.schemas.inventory import StockAdjustmentCreate, StockMovementRead
from app.schemas.product import (
    ProductCreate,
    ProductRead,
    ProductSort,
    ProductUpdate,
    StockStatus,
)
from app.services import inventory as inventory_service
from app.services import products as service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=Page[ProductRead])
def list_products(
    db: DbSession,
    org: CurrentOrg,
    q: Annotated[str | None, Query(max_length=100, description="Name, SKU or barcode")] = None,
    category_id: uuid.UUID | None = None,
    status: StockStatus | None = None,
    include_archived: bool = False,
    sort: ProductSort = "name",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = service.list_products(
        db,
        org.id,
        q=q.strip() if q else None,
        category_id=category_id,
        status=status,
        include_archived=include_archived,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, db: DbSession, auth: CanManageInventory):
    return service.create_product(db, auth.organization, data, created_by=auth.user.id)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: uuid.UUID, db: DbSession, org: CurrentOrg):
    return service.get_product(db, org.id, product_id)


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: uuid.UUID, data: ProductUpdate, db: DbSession, auth: CanManageInventory
):
    return service.update_product(db, auth.organization.id, product_id, data)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_product(product_id: uuid.UUID, db: DbSession, auth: CanManageInventory) -> Response:
    """Archives the product (soft delete). History is kept."""
    service.archive_product(db, auth.organization.id, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Stock ───────────────────────────────────────────────────────────────────


@router.post(
    "/{product_id}/stock-adjustments",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Replayed request: the original movement is returned"}},
)
def adjust_stock(
    product_id: uuid.UUID,
    data: StockAdjustmentCreate,
    db: DbSession,
    auth: CanManageInventory,
    response: Response,
    idempotency_key: Annotated[
        str | None,
        Header(max_length=80, description="Send the same key when retrying the same change"),
    ] = None,
):
    # A blank header means "no key", never a key of "" shared by every request.
    key = idempotency_key.strip() if idempotency_key else None
    movement, created = inventory_service.apply_stock_change(
        db,
        org_id=auth.organization.id,
        product_id=product_id,
        quantity_change=data.quantity_change,
        reason=data.reason,
        note=data.note,
        idempotency_key=key or None,
        created_by=auth.user.id,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return movement


@router.get("/{product_id}/movements", response_model=Page[StockMovementRead])
def list_movements(
    product_id: uuid.UUID,
    db: DbSession,
    org: CurrentOrg,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    service.get_product(db, org.id, product_id)  # 404 if not in this organization
    items, total = inventory_service.list_movements(
        db, org_id=org.id, product_id=product_id, limit=limit, offset=offset
    )
    return Page(items=items, total=total, limit=limit, offset=offset)
