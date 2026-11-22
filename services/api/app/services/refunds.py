"""Refunds. Every refund goes through `create_refund`.

Why this shape:
- The sale row is locked (SELECT ... FOR UPDATE) before anything is checked, so two refunds on
  the same receipt run one after the other: the second sees what the first already refunded and
  can't refund the same units again. The CHECK `quantity_refunded <= quantity` on sale_lines is
  the last line of defense if this code is ever wrong.
- Amounts come from the receipt lines (price and cost copied at checkout), never from the client.
- The refund, its lines, the stock movements, the sale's refunded figures and the refund counter
  are written in one transaction: all or nothing.
- Lock order is sale -> products -> organization. Checkout locks products -> organization and
  never locks an existing sale, so the two can't deadlock.
- An optional idempotency key makes a retried refund return the original instead of paying twice.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InvalidInputError, NotFoundError
from app.models import (
    AuditAction,
    MovementReason,
    Organization,
    Product,
    Refund,
    RefundLine,
    Sale,
)
from app.schemas.sale import RefundCreate
from app.services.audit import money, record
from app.services.inventory import record_movement

CENT = Decimal("0.01")
ZERO = Decimal("0")


def _find_by_key(db: Session, org_id: uuid.UUID, key: str) -> Refund | None:
    return db.scalar(
        select(Refund).where(Refund.organization_id == org_id, Refund.idempotency_key == key)
    )


def _replayed(db: Session, org_id: uuid.UUID, sale_id: uuid.UUID, key: str) -> Sale | None:
    """The sale a key was already used on, or None. A key reused on another sale is an error."""
    refund = _find_by_key(db, org_id, key)
    if refund is None:
        return None
    if refund.sale_id != sale_id:
        raise ConflictError("This Idempotency-Key was already used for another receipt.")
    return db.get(Sale, sale_id)


def create_refund(
    db: Session,
    *,
    org_id: uuid.UUID,
    sale_id: uuid.UUID,
    data: RefundCreate,
    user_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> tuple[Sale, bool]:
    """Refund units from one receipt. Returns (sale, created); created is False on a replay."""
    if idempotency_key and (sale := _replayed(db, org_id, sale_id, idempotency_key)):
        return sale, False

    sale = db.scalar(
        select(Sale)
        .where(Sale.id == sale_id, Sale.organization_id == org_id)
        .with_for_update(of=Sale)
        # Read the lines again after the lock, not from an earlier load in this session.
        .execution_options(populate_existing=True)
    )
    if sale is None:
        raise NotFoundError("Receipt not found.")

    by_id = {line.id: line for line in sale.lines}
    seen: set[uuid.UUID] = set()
    for line in data.lines:
        if line.sale_line_id in seen:
            raise InvalidInputError(
                "Each item can appear only once.", fields={str(line.sale_line_id): "Repeated"}
            )
        seen.add(line.sale_line_id)
    unknown = [line.sale_line_id for line in data.lines if line.sale_line_id not in by_id]
    if unknown:
        raise InvalidInputError(
            "An item isn't on this receipt.", fields={str(unknown[0]): "Not on this receipt"}
        )

    over: dict[str, str] = {}
    for line in data.lines:
        sold = by_id[line.sale_line_id]
        left = sold.quantity - sold.quantity_refunded
        if line.quantity > left:
            over[str(line.sale_line_id)] = (
                "Already fully refunded" if left == 0 else f"Only {left} left to refund"
            )
    if over:
        raise ConflictError("More than is left to refund. Check the quantities.", fields=over)

    restock_ids = sorted(
        {by_id[line.sale_line_id].product_id for line in data.lines if line.restock}
    )
    products = {
        p.id: p
        for p in db.scalars(
            select(Product)
            .where(Product.organization_id == org_id, Product.id.in_(restock_ids))
            .order_by(Product.id)  # same global lock order as checkout and receiving
            .with_for_update(of=Product)
        )
    }

    org = db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
    assert org is not None
    org.last_refund_number += 1

    ordered = sorted(data.lines, key=lambda line: by_id[line.sale_line_id].position)
    total = sum((by_id[line.sale_line_id].unit_price * line.quantity for line in ordered), ZERO)
    restocked_cost = sum(
        (by_id[line.sale_line_id].unit_cost * line.quantity for line in ordered if line.restock),
        ZERO,
    )

    refund = Refund(
        organization_id=org_id,
        sale_id=sale.id,
        refund_number=org.last_refund_number,
        total=total.quantize(CENT),
        restocked_cost=restocked_cost.quantize(CENT),
        currency=sale.currency,
        payment_method=sale.payment_method,
        reason=data.reason,
        note=data.note or None,
        idempotency_key=idempotency_key,
        created_by_user_id=user_id,
    )
    db.add(refund)
    db.flush()

    for line in ordered:
        sold = by_id[line.sale_line_id]
        db.add(
            RefundLine(
                refund_id=refund.id,
                sale_line_id=sold.id,
                position=sold.position,
                product_id=sold.product_id,
                quantity=line.quantity,
                unit_price=sold.unit_price,
                unit_cost=sold.unit_cost,
                line_total=(sold.unit_price * line.quantity).quantize(CENT),
                restocked=line.restock,
            )
        )
        sold.quantity_refunded += line.quantity
        if line.restock:
            # Archived products are restocked too: the units are physically back on the shelf.
            movement = record_movement(
                db,
                product=products[sold.product_id],
                quantity_change=line.quantity,
                reason=MovementReason.RETURN,
                note=f"Refund {refund.refund_code} on {sale.receipt_code}",
                created_by=user_id,
            )
            movement.refund_id = refund.id
    sale.refunded_total = (sale.refunded_total + refund.total).quantize(CENT)
    units = sum(line.quantity for line in ordered)
    record(
        db,
        org_id=org_id,
        actor_id=user_id,
        action=AuditAction.REFUND_CREATED,
        entity_type="refund",
        entity_id=refund.id,
        summary=(
            f"Refunded {money(refund.total, refund.currency)} on {sale.receipt_code} "
            f"({refund.refund_code}): {units} {'unit' if units == 1 else 'units'}, "
            f"{data.reason.replace('_', ' ')}"
        ),
        details={
            "refund_code": refund.refund_code,
            "receipt_code": sale.receipt_code,
            "sale_id": str(sale.id),
            "total": str(refund.total),
            "units": units,
            "restocked_units": sum(line.quantity for line in ordered if line.restock),
            "reason": str(data.reason),
        },
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key and (winner := _replayed(db, org_id, sale_id, idempotency_key)):
            return winner, False
        raise
    db.refresh(sale)
    return sale, True
