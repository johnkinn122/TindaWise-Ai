"""Purchase orders: draft → approved (owner) → received in one or more deliveries.

Why this shape:
- Every state change locks the order row (SELECT ... FOR UPDATE) first, so two people approving,
  receiving or cancelling at once are applied one after the other, never interleaved.
- Receiving locks the products in id order (the same global order as checkout), adds stock
  through `record_movement` (the only way stock changes), sets each product's cost to the
  order's unit cost (latest-cost rule), and commits everything in one transaction.
- Retried requests are safe: "create" and "receive" accept an Idempotency-Key, stored under a
  unique constraint, and a replay returns the original result.
- Lines copy the product's name, SKU and unit when written, so an order reads the same later.
"""

import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from app.models import (
    AuditAction,
    MovementReason,
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderReceipt,
    PurchaseOrderStatus,
    Role,
    StockMovement,
    Supplier,
    User,
)
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderEvent,
    PurchaseOrderLineInput,
    PurchaseOrderRead,
    PurchaseOrderReceiptRead,
    PurchaseOrderSummary,
    PurchaseOrderUpdate,
    ReceiptLineRead,
    ReceiveInput,
)
from app.services.audit import money, record
from app.services.inventory import record_movement
from app.services.reorder import reorder_candidates

CENT = Decimal("0.01")
MAX_LINES = 200

Status = PurchaseOrderStatus
RECEIVABLE = {Status.APPROVED.value, Status.PARTIALLY_RECEIVED.value}


def _now() -> datetime:
    return datetime.now(UTC)


# ── Lookups ─────────────────────────────────────────────────────────────────


def get_purchase_order(
    db: Session, org_id: uuid.UUID, po_id: uuid.UUID, *, lock: bool = False
) -> PurchaseOrder:
    query = select(PurchaseOrder).where(
        PurchaseOrder.id == po_id, PurchaseOrder.organization_id == org_id
    )
    if lock:
        # populate_existing: re-read the row after waiting for the lock, never a stale copy.
        query = query.with_for_update(of=PurchaseOrder).execution_options(populate_existing=True)
    po = db.scalar(query)
    if po is None:
        raise NotFoundError("Purchase order not found.")
    return po


def _active_supplier(db: Session, org_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier:
    supplier = db.scalar(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == org_id)
    )
    if supplier is None:
        raise NotFoundError("Supplier not found.", fields={"supplier_id": "Supplier not found"})
    if not supplier.is_active:
        raise ConflictError(
            f"{supplier.name} is archived. Choose another supplier.",
            fields={"supplier_id": "Supplier is archived"},
        )
    return supplier


def _build_lines(
    db: Session, org_id: uuid.UUID, inputs: list[PurchaseOrderLineInput]
) -> list[PurchaseOrderLine]:
    """Validate the requested lines against this organization's active products."""
    repeated = [pid for pid, n in Counter(line.product_id for line in inputs).items() if n > 1]
    if repeated:
        raise InvalidInputError(
            "Each product can appear only once. Change the quantity instead.",
            fields={"lines": "A product appears twice"},
        )
    products = {
        p.id: p
        for p in db.scalars(
            select(Product).where(
                Product.organization_id == org_id,
                Product.id.in_([line.product_id for line in inputs]),
            )
        )
    }
    if any(line.product_id not in products for line in inputs):
        raise NotFoundError("A product on this order no longer exists. Remove it and try again.")
    archived = [p.name for p in products.values() if not p.is_active]
    if archived:
        raise ConflictError(f"{archived[0]} is archived and can't be ordered.")

    lines = []
    for position, line in enumerate(inputs, start=1):
        product = products[line.product_id]
        unit_cost = line.unit_cost if line.unit_cost is not None else product.cost
        lines.append(
            PurchaseOrderLine(
                position=position,
                product_id=product.id,
                product_name=product.name,
                sku=product.sku,
                unit=product.unit,
                quantity_ordered=line.quantity,
                quantity_received=0,
                unit_cost=unit_cost,
                line_total=(unit_cost * line.quantity).quantize(CENT),
            )
        )
    return lines


def _replace_lines(db: Session, po: PurchaseOrder, lines: list[PurchaseOrderLine]) -> None:
    po.lines.clear()
    # Delete the old rows before inserting the new ones: (order, product) and (order, position)
    # are unique, and the unit of work would otherwise insert first.
    db.flush()
    po.lines.extend(lines)
    po.total = sum((line.line_total for line in lines), Decimal("0")).quantize(CENT)


def _require_status(po: PurchaseOrder, allowed: set[str], action: str) -> None:
    if po.status not in allowed:
        label = po.status.replace("_", " ")
        raise ConflictError(f"{po.code} is {label}, so it can't be {action}.")


# ── Create and edit drafts ──────────────────────────────────────────────────


def _find_by_key(db: Session, org_id: uuid.UUID, key: str) -> PurchaseOrder | None:
    return db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.organization_id == org_id, PurchaseOrder.idempotency_key == key
        )
    )


def create_purchase_order(
    db: Session,
    *,
    org_id: uuid.UUID,
    data: PurchaseOrderCreate,
    user_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> tuple[PurchaseOrder, bool]:
    """Create a draft. Returns (order, created); created is False for a replayed key."""
    if idempotency_key and (existing := _find_by_key(db, org_id, idempotency_key)):
        return existing, False
    if data.supplier_id is not None:
        _active_supplier(db, org_id, data.supplier_id)
    lines = _build_lines(db, org_id, data.lines)

    # Next order number for this store, under a lock on the organization row.
    org = db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
    assert org is not None
    org.last_po_number += 1

    po = PurchaseOrder(
        organization_id=org_id,
        po_number=org.last_po_number,
        supplier_id=data.supplier_id,
        status=Status.DRAFT.value,
        currency=org.currency,
        expected_on=data.expected_on,
        notes=data.notes,
        idempotency_key=idempotency_key,
        created_by_user_id=user_id,
    )
    db.add(po)
    _replace_lines(db, po, lines)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key and (winner := _find_by_key(db, org_id, idempotency_key)):
            return winner, False
        raise
    db.refresh(po)
    return po, True


def create_from_reorder(
    db: Session,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> tuple[PurchaseOrder, bool]:
    """A draft holding every current reorder suggestion at today's product costs. The supplier
    is chosen while reviewing the draft, before the owner approves it."""
    if idempotency_key and (existing := _find_by_key(db, org_id, idempotency_key)):
        return existing, False
    org = db.get(Organization, org_id)
    assert org is not None
    candidates = reorder_candidates(db, org, now or _now())
    if not candidates:
        raise ConflictError("Nothing needs reordering right now.")
    data = PurchaseOrderCreate(
        lines=[
            PurchaseOrderLineInput(product_id=c.product.id, quantity=c.quantity)
            for c in candidates[:MAX_LINES]
        ],
        notes="Drafted from the Overview's reorder suggestions.",
    )
    return create_purchase_order(
        db, org_id=org_id, data=data, user_id=user_id, idempotency_key=idempotency_key
    )


def update_draft(
    db: Session, org_id: uuid.UUID, po_id: uuid.UUID, data: PurchaseOrderUpdate
) -> PurchaseOrder:
    po = get_purchase_order(db, org_id, po_id, lock=True)
    _require_status(po, {Status.DRAFT.value}, "edited")
    changes = data.model_dump(exclude_unset=True)
    if "supplier_id" in changes:
        if changes["supplier_id"] is not None:
            _active_supplier(db, org_id, changes["supplier_id"])
        po.supplier_id = changes["supplier_id"]
    if "expected_on" in changes:
        po.expected_on = changes["expected_on"]
    if "notes" in changes:
        po.notes = changes["notes"]
    if data.lines is not None:
        _replace_lines(db, po, _build_lines(db, org_id, data.lines))
    db.commit()
    db.refresh(po)
    return po


# ── Status changes ──────────────────────────────────────────────────────────


def _audit(
    db: Session, po: PurchaseOrder, user_id: uuid.UUID, action: AuditAction, summary: str,
    details: dict,
) -> None:  # fmt: skip
    record(
        db,
        org_id=po.organization_id,
        actor_id=user_id,
        action=action,
        entity_type="purchase_order",
        entity_id=po.id,
        summary=summary,
        details={"code": po.code, **details},
    )


def approve(db: Session, org_id: uuid.UUID, po_id: uuid.UUID, user_id: uuid.UUID) -> PurchaseOrder:
    """Owner only (checked by the endpoint). Locks the lines: nothing changes after approval."""
    po = get_purchase_order(db, org_id, po_id, lock=True)
    _require_status(po, {Status.DRAFT.value}, "approved")
    if po.supplier_id is None:
        raise InvalidInputError(
            "Choose a supplier before approving.", fields={"supplier_id": "Choose a supplier"}
        )
    supplier = _active_supplier(db, org_id, po.supplier_id)
    po.status = Status.APPROVED.value
    po.approved_by_user_id = user_id
    po.approved_at = _now()
    total = sum((line.line_total for line in po.lines), Decimal("0"))
    _audit(
        db, po, user_id, AuditAction.PURCHASE_ORDER_APPROVED,
        f"Approved {po.code} for {money(total, po.currency)} from {supplier.name}",
        {"total": str(total), "supplier": supplier.name},
    )  # fmt: skip
    db.commit()
    db.refresh(po)
    return po


def cancel(db: Session, org_id: uuid.UUID, po_id: uuid.UUID, user_id: uuid.UUID, role: Role):
    """Drafts: owners and managers. Approved orders with nothing received: owners only, since
    the owner approved them. Anything already received is closed instead, never cancelled."""
    po = get_purchase_order(db, org_id, po_id, lock=True)
    _require_status(po, {Status.DRAFT.value, Status.APPROVED.value}, "cancelled")
    if po.status == Status.APPROVED.value and role != Role.OWNER:
        raise ForbiddenError("Only the owner can cancel an approved purchase order.")
    _audit(
        db, po, user_id, AuditAction.PURCHASE_ORDER_CANCELLED,
        f"Cancelled {po.code} ({'approved' if po.status == Status.APPROVED.value else 'draft'})",
        {"status_before": po.status},
    )  # fmt: skip
    po.status = Status.CANCELLED.value
    po.finished_by_user_id = user_id
    po.finished_at = _now()
    db.commit()
    db.refresh(po)
    return po


def close_short(
    db: Session, org_id: uuid.UUID, po_id: uuid.UUID, user_id: uuid.UUID
) -> PurchaseOrder:
    """The rest of a partly delivered order will not come. What arrived stays in stock."""
    po = get_purchase_order(db, org_id, po_id, lock=True)
    _require_status(po, {Status.PARTIALLY_RECEIVED.value}, "closed")
    ordered = sum(line.quantity_ordered for line in po.lines)
    received = sum(line.quantity_received for line in po.lines)
    _audit(
        db, po, user_id, AuditAction.PURCHASE_ORDER_CLOSED,
        f"Closed {po.code} short: {received} of {ordered} units received",
        {"units_ordered": ordered, "units_received": received},
    )  # fmt: skip
    po.status = Status.CLOSED.value
    po.finished_by_user_id = user_id
    po.finished_at = _now()
    db.commit()
    db.refresh(po)
    return po


# ── Receiving ───────────────────────────────────────────────────────────────


def _receipt_by_key(db: Session, org_id: uuid.UUID, key: str) -> PurchaseOrderReceipt | None:
    return db.scalar(
        select(PurchaseOrderReceipt).where(
            PurchaseOrderReceipt.organization_id == org_id,
            PurchaseOrderReceipt.idempotency_key == key,
        )
    )


def _replayed(db: Session, org_id: uuid.UUID, po_id: uuid.UUID, key: str) -> PurchaseOrder | None:
    receipt = _receipt_by_key(db, org_id, key)
    if receipt is None:
        return None
    if receipt.purchase_order_id != po_id:
        raise ConflictError("This request key was already used for a different purchase order.")
    return get_purchase_order(db, org_id, po_id)


def receive(
    db: Session,
    *,
    org_id: uuid.UUID,
    po_id: uuid.UUID,
    data: ReceiveInput,
    user_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> tuple[PurchaseOrder, bool]:
    """Record one delivery. Returns (order, created); created is False for a replayed key."""
    if idempotency_key and (po := _replayed(db, org_id, po_id, idempotency_key)):
        return po, False

    po = get_purchase_order(db, org_id, po_id, lock=True)
    _require_status(po, RECEIVABLE, "received")

    by_id = {line.id: line for line in po.lines}
    requested = Counter(line.line_id for line in data.lines)
    if any(n > 1 for n in requested.values()):
        raise InvalidInputError("Each line can appear only once.", fields={"lines": "Repeated"})
    unknown = [line.line_id for line in data.lines if line.line_id not in by_id]
    if unknown:
        raise InvalidInputError(
            "A line doesn't belong to this purchase order.", fields={str(unknown[0]): "Unknown"}
        )
    over: dict[str, str] = {}
    for line in data.lines:
        remaining = by_id[line.line_id].quantity_ordered - by_id[line.line_id].quantity_received
        if line.quantity > remaining:
            over[str(line.line_id)] = f"Only {remaining} left to receive"
    if over:
        raise InvalidInputError("More than was ordered. Check the quantities.", fields=over)
    arriving = {line.line_id: line.quantity for line in data.lines if line.quantity > 0}
    if not arriving:
        raise InvalidInputError("Enter how many arrived for at least one product.")

    receipt = PurchaseOrderReceipt(
        organization_id=org_id,
        purchase_order_id=po.id,
        note=data.note or None,
        idempotency_key=idempotency_key,
        created_by_user_id=user_id,
    )
    db.add(receipt)
    db.flush()

    product_ids = sorted({by_id[line_id].product_id for line_id in arriving})
    products = {
        p.id: p
        for p in db.scalars(
            select(Product)
            .where(Product.organization_id == org_id, Product.id.in_(product_ids))
            .order_by(Product.id)  # one global lock order prevents deadlocks with checkout
            .with_for_update(of=Product)
        )
    }
    for line_id, quantity in arriving.items():
        line = by_id[line_id]
        product = products[line.product_id]
        line.quantity_received += quantity
        product.cost = line.unit_cost  # latest-cost rule; past sales keep their own cost
        movement = record_movement(
            db,
            product=product,
            quantity_change=quantity,
            reason=MovementReason.PURCHASE,
            note=f"Received on {po.code}",
            created_by=user_id,
        )
        movement.purchase_order_receipt_id = receipt.id

    if all(line.quantity_received == line.quantity_ordered for line in po.lines):
        po.status = Status.RECEIVED.value
        po.finished_by_user_id = user_id
        po.finished_at = _now()
    else:
        po.status = Status.PARTIALLY_RECEIVED.value

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key and (winner := _replayed(db, org_id, po_id, idempotency_key)):
            return winner, False
        raise
    db.refresh(po)
    return po, True


# ── Reading ─────────────────────────────────────────────────────────────────


def list_purchase_orders(
    db: Session,
    org_id: uuid.UUID,
    *,
    statuses: list[str] | None,
    supplier_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[PurchaseOrderSummary], int]:
    query = select(PurchaseOrder).where(PurchaseOrder.organization_id == org_id)
    if statuses:
        query = query.where(PurchaseOrder.status.in_(statuses))
    if supplier_id:
        query = query.where(PurchaseOrder.supplier_id == supplier_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.po_number.desc())
        .limit(limit)
        .offset(offset)
    )
    return [summarize(po) for po in rows], total


def summarize(po: PurchaseOrder) -> PurchaseOrderSummary:
    return PurchaseOrderSummary(
        id=po.id,
        code=po.code,
        status=po.status,
        supplier=po.supplier,
        total=po.total,
        currency=po.currency,
        line_count=len(po.lines),
        expected_on=po.expected_on,
        created_at=po.created_at,
    )


def to_read(db: Session, po: PurchaseOrder) -> PurchaseOrderRead:
    """The full order with its deliveries and a readable history (names, not ids)."""
    receipt_ids = [r.id for r in po.receipts]
    movements = (
        db.scalars(
            select(StockMovement)
            .where(StockMovement.purchase_order_receipt_id.in_(receipt_ids))
            .order_by(StockMovement.created_at, StockMovement.id)
        ).all()
        if receipt_ids
        else []
    )
    user_ids = {
        po.created_by_user_id,
        po.approved_by_user_id,
        po.finished_by_user_id,
        *(r.created_by_user_id for r in po.receipts),
    } - {None}
    names = (
        dict(db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all())
        if user_ids
        else {}
    )
    product_names = {line.product_id: line.product_name for line in po.lines}
    # Movements in one delivery share a timestamp; list them in the order's line order.
    positions = {line.product_id: line.position for line in po.lines}
    movements = sorted(movements, key=lambda m: (m.created_at, positions.get(m.product_id, 0)))

    receipts = [
        PurchaseOrderReceiptRead(
            id=r.id,
            note=r.note,
            created_at=r.created_at,
            received_by=names.get(r.created_by_user_id),
            lines=[
                ReceiptLineRead(
                    product_id=m.product_id,
                    product_name=product_names.get(m.product_id, "Product"),
                    quantity=m.quantity_change,
                )
                for m in movements
                if m.purchase_order_receipt_id == r.id
            ],
        )
        for r in po.receipts
    ]

    history = [
        PurchaseOrderEvent(action="created", at=po.created_at, by=names.get(po.created_by_user_id))
    ]
    if po.approved_at:
        history.append(
            PurchaseOrderEvent(
                action="approved", at=po.approved_at, by=names.get(po.approved_by_user_id)
            )
        )
    history += [
        PurchaseOrderEvent(action="received", at=r.created_at, by=r.received_by) for r in receipts
    ]
    if po.finished_at and po.status in (Status.CLOSED.value, Status.CANCELLED.value):
        history.append(
            PurchaseOrderEvent(
                action=po.status, at=po.finished_at, by=names.get(po.finished_by_user_id)
            )
        )

    return PurchaseOrderRead(
        **summarize(po).model_dump(),
        notes=po.notes,
        lines=po.lines,
        receipts=receipts,
        history=history,
        updated_at=po.updated_at,
    )
