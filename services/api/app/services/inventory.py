"""Inventory rules: every stock change goes through `apply_stock_change`.

Why this shape:
- The product row is locked with SELECT ... FOR UPDATE, so two cashiers selling the last item
  at the same moment are serialized: the second one sees the updated balance and is rejected
  instead of driving stock below zero.
- The balance update and the ledger row are written in one transaction: both happen or neither.
- An optional idempotency key makes retries safe: the same key never applies twice.
- The database CHECK (stock_on_hand >= 0) is the last line of defense if code is ever wrong.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InsufficientStockError, NotFoundError
from app.models import MovementReason, Product, StockMovement


def _find_by_idempotency_key(db: Session, org_id: uuid.UUID, key: str) -> StockMovement | None:
    return db.scalar(
        select(StockMovement).where(
            StockMovement.organization_id == org_id, StockMovement.idempotency_key == key
        )
    )


def record_movement(
    db: Session,
    *,
    product: Product,
    quantity_change: int,
    reason: MovementReason,
    note: str | None = None,
    idempotency_key: str | None = None,
    created_by: uuid.UUID | None = None,
) -> StockMovement:
    """Apply a change to a product that the caller has already locked. Does not commit."""
    new_balance = product.stock_on_hand + quantity_change
    if new_balance < 0:
        raise InsufficientStockError(
            f"Only {product.stock_on_hand} {product.unit} of {product.name} in stock. "
            f"Cannot remove {abs(quantity_change)}.",
            fields={"quantity_change": "More than the stock on hand"},
        )
    product.stock_on_hand = new_balance
    movement = StockMovement(
        organization_id=product.organization_id,
        product_id=product.id,
        quantity_change=quantity_change,
        balance_after=new_balance,
        reason=reason.value,
        note=note,
        idempotency_key=idempotency_key,
        created_by_user_id=created_by,
    )
    db.add(movement)
    return movement


def apply_stock_change(
    db: Session,
    *,
    org_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity_change: int,
    reason: MovementReason,
    note: str | None = None,
    idempotency_key: str | None = None,
    created_by: uuid.UUID | None = None,
) -> tuple[StockMovement, bool]:
    """Change stock safely. Returns (movement, created). `created` is False on a replayed key."""
    if idempotency_key:
        existing = _find_by_idempotency_key(db, org_id, idempotency_key)
        if existing:
            if existing.product_id != product_id:
                raise ConflictError("This Idempotency-Key was already used for another product.")
            return existing, False

    product = db.scalar(
        select(Product)
        .where(Product.id == product_id, Product.organization_id == org_id)
        .with_for_update(of=Product)  # lock only the product row, not the joined category
    )
    if product is None:
        raise NotFoundError("Product not found.")
    if not product.is_active:
        raise ConflictError("This product is archived. Restore it before changing its stock.")

    movement = record_movement(
        db,
        product=product,
        quantity_change=quantity_change,
        reason=reason,
        note=note,
        idempotency_key=idempotency_key,
        created_by=created_by,
    )
    try:
        db.commit()
    except IntegrityError:
        # Two requests with the same key raced past the first check; the loser lands here.
        db.rollback()
        if idempotency_key and (winner := _find_by_idempotency_key(db, org_id, idempotency_key)):
            return winner, False
        raise
    return movement, True


def list_movements(
    db: Session, *, org_id: uuid.UUID, product_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[StockMovement], int]:
    base = select(StockMovement).where(
        StockMovement.organization_id == org_id, StockMovement.product_id == product_id
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total
