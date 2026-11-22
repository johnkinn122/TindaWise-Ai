from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CanManageInventory, DbSession
from app.schemas.report import Preset, ProductSort, SalesReport
from app.services import reports as service

# Owners and managers only: the report is built on costs and profit, which cashiers don't see.
router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/sales", response_model=SalesReport)
def sales_report(
    db: DbSession,
    auth: CanManageInventory,
    preset: Preset | None = None,
    start: Annotated[date | None, Query(description="First day, store time (with `end`)")] = None,
    end: Annotated[date | None, Query(description="Last day, included")] = None,
    product_sort: ProductSort = "sales",
    top: Annotated[int, Query(ge=1, le=500, description="How many top products to list")] = 10,
):
    """Sales, profit and purchases for a period, against the period of equal length before it.
    A custom `start`/`end` wins over `preset`; with neither, the last 7 days."""
    return service.build_sales_report(
        db,
        auth.organization,
        preset=preset,
        start=start,
        end=end,
        product_sort=product_sort,
        top=top,
    )
