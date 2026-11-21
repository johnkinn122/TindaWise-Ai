"""Checkout. Every sale goes through `create_sale`.

Why this shape:
- Prices and costs are read from the database, never from the client.
- All products in the cart are locked (SELECT ... FOR UPDATE) in id order before any stock is
  checked, so two checkouts touching the same products wait for each other instead of
  overselling or deadlocking.
- The sale, its lines, the stock movements and the receipt counter are written in one
  transaction: if one item is short, nothing is recorded.
- An optional idempotency key makes a retried checkout return the original sale.
"""

import uuid
from collections import OrderedDict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InsufficientStockError, InvalidInputError, NotFoundError
from app.models import MovementReason, Organization, Product, Sale, SaleLine, User
from app.schemas.sale import SaleCreate
from app.services.inventory import record_movement

CENT = Decimal("0.01")


def _find_by_key(db: Session, org_id: uuid.UUID, key: str) -> Sale | None:
    return db.scalar(
        select(Sale).where(Sale.organization_id == org_id, Sale.idempotency_key == key)
    )


def create_sale(
    db: Session,
    *,
    org_id: uuid.UUID,
    data: SaleCreate,
    cashier_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> tuple[Sale, bool]:
    """Record a sale. Returns (sale, created); created is False for a replayed key."""
    if idempotency_key and (existing := _find_by_key(db, org_id, idempotency_key)):
        return existing, False

    # Merge repeated products (scanning the same item twice) into one line, keeping cart order.
    quantities: OrderedDict[uuid.UUID, int] = OrderedDict()
    for line in data.lines:
        quantities[line.product_id] = quantities.get(line.product_id, 0) + line.quantity

    products = {
        p.id: p
        for p in db.scalars(
            select(Product)
            .where(Product.organization_id == org_id, Product.id.in_(quantities))
            .order_by(Product.id)  # one global lock order prevents deadlocks
            .with_for_update(of=Product)
        )
    }
    missing = [pid for pid in quantities if pid not in products]
    if missing:
        raise NotFoundError("A product in the cart no longer exists. Remove it and try again.")
    archived = [products[pid].name for pid in quantities if not products[pid].is_active]
    if archived:
        raise ConflictError(f"{archived[0]} is archived and can't be sold.")

    short = [
        (products[pid], qty) for pid, qty in quantities.items() if products[pid].stock_on_hand < qty
    ]
    if short:
        product, qty = short[0]
        raise InsufficientStockError(
            f"Only {product.stock_on_hand} {product.unit} of {product.name} left; "
            f"the cart has {qty}.",
            fields={str(product.id): f"Only {product.stock_on_hand} left"},
        )

    total = sum((products[pid].price * qty for pid, qty in quantities.items()), Decimal("0"))
    cost_total = sum((products[pid].cost * qty for pid, qty in quantities.items()), Decimal("0"))

    amount_tendered = change_due = None
    if data.payment_method == "cash":
        amount_tendered = data.amount_tendered
        if amount_tendered is None or amount_tendered < total:
            raise InvalidInputError(
                f"Cash received is less than the total of ₱{total:,.2f}.",
                fields={"amount_tendered": "Less than the total"},
            )
        change_due = (amount_tendered - total).quantize(CENT)

    # Next receipt number for this store, under a lock on the organization row.
    org = db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
    assert org is not None
    org.last_receipt_number += 1

    sale = Sale(
        organization_id=org_id,
        receipt_number=org.last_receipt_number,
        total=total.quantize(CENT),
        cost_total=cost_total.quantize(CENT),
        currency=org.currency,
        payment_method=data.payment_method,
        amount_tendered=amount_tendered,
        change_due=change_due,
        payment_reference=data.payment_reference if data.payment_method == "e_wallet" else None,
        idempotency_key=idempotency_key,
        created_by_user_id=cashier_id,
    )
    db.add(sale)
    db.flush()

    for position, (pid, qty) in enumerate(quantities.items(), start=1):
        product = products[pid]
        db.add(
            SaleLine(
                sale_id=sale.id,
                position=position,
                product_id=pid,
                product_name=product.name,
                sku=product.sku,
                unit=product.unit,
                unit_price=product.price,
                unit_cost=product.cost,
                quantity=qty,
                line_total=(product.price * qty).quantize(CENT),
            )
        )
        movement = record_movement(
            db,
            product=product,
            quantity_change=-qty,
            reason=MovementReason.SALE,
            note=f"Receipt {sale.receipt_code}",
            created_by=cashier_id,
        )
        movement.sale_id = sale.id

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key and (winner := _find_by_key(db, org_id, idempotency_key)):
            return winner, False
        raise
    db.refresh(sale)
    return sale, True


def get_sale(db: Session, org_id: uuid.UUID, sale_id: uuid.UUID) -> Sale:
    sale = db.scalar(select(Sale).where(Sale.id == sale_id, Sale.organization_id == org_id))
    if sale is None:
        raise NotFoundError("Receipt not found.")
    return sale


def cashier_names(db: Session, user_ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all())


def list_sales(
    db: Session,
    org_id: uuid.UUID,
    *,
    cashier_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Sale], int]:
    query = select(Sale).where(Sale.organization_id == org_id)
    if cashier_id:
        query = query.where(Sale.created_by_user_id == cashier_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Sale.created_at.desc(), Sale.receipt_number.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total
