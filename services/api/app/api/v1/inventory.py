import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CanManageInventory, DbSession
from app.models import MovementReason
from app.schemas.common import Page
from app.schemas.inventory import InventorySummary, LedgerEntry
from app.services import inventory_ledger as service

# Owners and managers only: the ledger shows who changed stock, and the summary shows stock value
# at cost. Cashiers see stock levels on the product list instead.
router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/movements", response_model=Page[LedgerEntry])
def list_movements(
    db: DbSession,
    auth: CanManageInventory,
    reason: MovementReason | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Product name or SKU")] = None,
    product_id: uuid.UUID | None = None,
    user_id: Annotated[uuid.UUID | None, Query(description="Who made the change")] = None,
    start: Annotated[date | None, Query(description="First day, store time")] = None,
    end: Annotated[date | None, Query(description="Last day, included")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Every stock movement in the store, newest first. Each one links to the sale, refund or
    delivery that caused it, when there was one."""
    filters = service.LedgerFilters(
        reason=reason,
        q=q.strip() if q and q.strip() else None,
        product_id=product_id,
        user_id=user_id,
        start=start,
        end=end,
    )
    items, total = service.list_ledger(db, auth.organization, filters, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/summary", response_model=InventorySummary)
def inventory_summary(db: DbSession, auth: CanManageInventory):
    """Units on hand, stock value at current cost, and low / out-of-stock counts."""
    return service.stock_summary(db, auth.organization)
