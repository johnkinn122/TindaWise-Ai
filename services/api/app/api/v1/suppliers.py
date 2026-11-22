import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CanManageInventory, DbSession
from app.schemas.common import Page
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from app.services import suppliers as service

# Owners and managers only: suppliers come with prices and purchasing, which cashiers don't see.
router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=Page[SupplierRead])
def list_suppliers(
    db: DbSession,
    auth: CanManageInventory,
    q: Annotated[str | None, Query(max_length=100, description="Name, contact or phone")] = None,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = service.list_suppliers(
        db,
        auth.organization.id,
        q=q.strip() if q else None,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(data: SupplierCreate, db: DbSession, auth: CanManageInventory):
    return service.create_supplier(db, auth.organization.id, data)


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: uuid.UUID, db: DbSession, auth: CanManageInventory):
    return service.get_supplier(db, auth.organization.id, supplier_id)


@router.patch("/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: uuid.UUID, data: SupplierUpdate, db: DbSession, auth: CanManageInventory
):
    return service.update_supplier(db, auth.organization.id, supplier_id, data)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_supplier(supplier_id: uuid.UUID, db: DbSession, auth: CanManageInventory) -> Response:
    """Archives the supplier. Its purchase orders keep pointing at it."""
    service.archive_supplier(db, auth.organization.id, supplier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
