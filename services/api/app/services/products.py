"""Product and category rules. Every query is scoped to one organization."""

import uuid
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InvalidInputError, NotFoundError
from app.models import AuditAction, Category, MovementReason, Organization, Product
from app.schemas.category import CategoryCreate
from app.schemas.product import ProductCreate, ProductSort, ProductUpdate, StockStatus
from app.services.audit import money, record
from app.services.inventory import record_movement

_SORTS = {
    "name": Product.name.asc(),
    "-name": Product.name.desc(),
    "stock": Product.stock_on_hand.asc(),
    "-stock": Product.stock_on_hand.desc(),
    "price": Product.price.asc(),
    "-price": Product.price.desc(),
    "-updated": Product.updated_at.desc(),
}


# ── Categories ──────────────────────────────────────────────────────────────


def list_categories(db: Session, org_id: uuid.UUID) -> list[Category]:
    return list(
        db.scalars(
            select(Category).where(Category.organization_id == org_id).order_by(Category.name)
        )
    )


def create_category(db: Session, org_id: uuid.UUID, data: CategoryCreate) -> Category:
    category = Category(organization_id=org_id, name=data.name)
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            f"A category named “{data.name}” already exists.",
            fields={"name": "Already exists"},
        ) from exc
    return category


def _require_category(db: Session, org_id: uuid.UUID, category_id: uuid.UUID) -> None:
    exists = db.scalar(
        select(Category.id).where(Category.id == category_id, Category.organization_id == org_id)
    )
    if not exists:
        # Same message whether it doesn't exist or belongs to another organization.
        raise NotFoundError("Category not found.", fields={"category_id": "Category not found"})


# ── Products ────────────────────────────────────────────────────────────────


def _status_filter(query: Select, status: StockStatus) -> Select:
    if status == "out_of_stock":
        return query.where(Product.stock_on_hand == 0)
    if status == "low_stock":
        return query.where(
            Product.stock_on_hand > 0, Product.stock_on_hand <= Product.reorder_level
        )
    return query.where(Product.stock_on_hand > Product.reorder_level)


def list_products(
    db: Session,
    org_id: uuid.UUID,
    *,
    q: str | None,
    category_id: uuid.UUID | None,
    status: StockStatus | None,
    include_archived: bool,
    sort: ProductSort,
    limit: int,
    offset: int,
) -> tuple[list[Product], int]:
    query = select(Product).where(Product.organization_id == org_id)
    if not include_archived:
        query = query.where(Product.is_active.is_(True))
    if q:
        # Escape LIKE wildcards so a search for "50%" means the literal text.
        term = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(
                Product.name.ilike(term, escape="\\"),
                Product.sku.ilike(term, escape="\\"),
                Product.barcode.ilike(term, escape="\\"),
            )
        )
    if category_id:
        query = query.where(Product.category_id == category_id)
    if status:
        query = _status_filter(query, status)

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(query.order_by(_SORTS[sort], Product.id).limit(limit).offset(offset)).unique()
    return list(rows), total


def lookup_product(db: Session, org_id: uuid.UUID, code: str) -> Product:
    """Exact match on barcode, then SKU (case-insensitive). Used by barcode scanners at checkout."""
    code = code.strip()
    base = select(Product).where(Product.organization_id == org_id, Product.is_active.is_(True))
    product = db.scalar(base.where(Product.barcode == code)) or db.scalar(
        base.where(func.lower(Product.sku) == code.lower())
    )
    if product is None:
        raise NotFoundError(f"No product with barcode or SKU “{code}”.")
    return product


def get_product(db: Session, org_id: uuid.UUID, product_id: uuid.UUID) -> Product:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.organization_id == org_id)
    )
    if product is None:
        raise NotFoundError("Product not found.")
    return product


def _duplicate_error(exc: IntegrityError) -> ConflictError:
    message = str(exc.orig)
    if "barcode" in message:
        return ConflictError(
            "Another product already uses this barcode.",
            fields={"barcode": "Already used by another product"},
        )
    if "sku" in message:
        return ConflictError(
            "Another product already uses this SKU.",
            fields={"sku": "Already used by another product"},
        )
    return ConflictError("This product conflicts with an existing record.")


def create_product(
    db: Session, org: Organization, data: ProductCreate, *, created_by: uuid.UUID | None = None
) -> Product:
    if data.category_id:
        _require_category(db, org.id, data.category_id)

    product = Product(
        organization_id=org.id,
        category_id=data.category_id,
        name=data.name,
        sku=data.sku,
        barcode=data.barcode,
        unit=data.unit,
        price=data.price,
        cost=data.cost,
        currency=org.currency,
        reorder_level=data.reorder_level,
        stock_on_hand=0,
    )
    db.add(product)
    try:
        db.flush()  # get the id and surface duplicate SKU/barcode before writing stock
        if data.initial_stock > 0:
            record_movement(
                db,
                product=product,
                quantity_change=data.initial_stock,
                reason=MovementReason.INITIAL,
                created_by=created_by,
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_error(exc) from exc
    db.refresh(product)
    return product


def update_product(
    db: Session,
    org_id: uuid.UUID,
    product_id: uuid.UUID,
    data: ProductUpdate,
    *,
    actor_id: uuid.UUID,
) -> Product:
    product = get_product(db, org_id, product_id)
    changes = data.model_dump(exclude_unset=True)

    for required in ("name", "sku", "unit", "price", "cost", "reorder_level", "is_active"):
        if required in changes and changes[required] is None:
            raise InvalidInputError(
                f"{required} cannot be empty.", fields={required: "This field is required"}
            )
    if changes.get("category_id"):
        _require_category(db, org_id, changes["category_id"])

    money_changes = {
        field: [str(getattr(product, field)), str(changes[field])]
        for field in ("price", "cost")
        if field in changes and getattr(product, field) != changes[field]
    }
    for field, value in changes.items():
        setattr(product, field, value)
    if money_changes:
        parts = [
            f"{field} {money(Decimal(old), product.currency)} → "
            f"{money(Decimal(new), product.currency)}"
            for field, (old, new) in money_changes.items()
        ]
        record(
            db,
            org_id=org_id,
            actor_id=actor_id,
            action=AuditAction.PRODUCT_PRICE_CHANGED,
            entity_type="product",
            entity_id=product.id,
            summary=f"Changed {product.name}: " + "; ".join(parts),
            details={"sku": product.sku, "changes": money_changes},
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_error(exc) from exc
    db.refresh(product)
    return product


def archive_product(
    db: Session, org_id: uuid.UUID, product_id: uuid.UUID, *, actor_id: uuid.UUID
) -> None:
    """Products are archived, never deleted, so sales and stock history stay intact."""
    product = get_product(db, org_id, product_id)
    if product.is_active:  # archiving twice is harmless and logged once
        record(
            db,
            org_id=org_id,
            actor_id=actor_id,
            action=AuditAction.PRODUCT_ARCHIVED,
            entity_type="product",
            entity_id=product.id,
            summary=f"Archived {product.name} ({product.sku})",
            details={"sku": product.sku, "stock_on_hand": product.stock_on_hand},
        )
    product.is_active = False
    db.commit()
