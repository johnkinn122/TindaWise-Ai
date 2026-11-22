"""Supplier rules. Every query is scoped to one organization. Suppliers are archived, never
deleted, so old purchase orders keep pointing at them."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Supplier
from app.schemas.supplier import SupplierCreate, SupplierUpdate


def _name_taken(name: str) -> ConflictError:
    return ConflictError(
        f"A supplier named “{name}” already exists.", fields={"name": "Already exists"}
    )


def list_suppliers(
    db: Session,
    org_id: uuid.UUID,
    *,
    q: str | None,
    include_archived: bool,
    limit: int,
    offset: int,
) -> tuple[list[Supplier], int]:
    query = select(Supplier).where(Supplier.organization_id == org_id)
    if not include_archived:
        query = query.where(Supplier.is_active.is_(True))
    if q:
        # Escape LIKE wildcards so a search for "50%" means the literal text.
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(
                Supplier.name.ilike(pattern, escape="\\"),
                Supplier.contact_name.ilike(pattern, escape="\\"),
                Supplier.phone.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(func.lower(Supplier.name), Supplier.id).limit(limit).offset(offset)
    )
    return list(rows), total


def get_supplier(db: Session, org_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier:
    supplier = db.scalar(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == org_id)
    )
    if supplier is None:
        # Same answer whether it doesn't exist or belongs to another organization.
        raise NotFoundError("Supplier not found.", fields={"supplier_id": "Supplier not found"})
    return supplier


def create_supplier(db: Session, org_id: uuid.UUID, data: SupplierCreate) -> Supplier:
    supplier = Supplier(organization_id=org_id, **data.model_dump())
    db.add(supplier)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _name_taken(data.name) from exc
    db.refresh(supplier)
    return supplier


def update_supplier(
    db: Session, org_id: uuid.UUID, supplier_id: uuid.UUID, data: SupplierUpdate
) -> Supplier:
    supplier = get_supplier(db, org_id, supplier_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name") is None:
        changes.pop("name", None)  # a name can be changed, never removed
    if changes.get("is_active") is None:
        changes.pop("is_active", None)
    for field, value in changes.items():
        setattr(supplier, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _name_taken(changes["name"]) from exc
    db.refresh(supplier)
    return supplier


def archive_supplier(db: Session, org_id: uuid.UUID, supplier_id: uuid.UUID) -> None:
    supplier = get_supplier(db, org_id, supplier_id)
    supplier.is_active = False
    db.commit()
