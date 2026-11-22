from fastapi import APIRouter

from app.api.deps import Auth, DbSession, can_see_costs
from app.models import Role
from app.schemas.overview import Overview
from app.services import overview as service

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("", response_model=Overview)
def get_overview(db: DbSession, auth: Auth):
    """Every role can open it. Cashiers get their own sales and no cost or margin figures."""
    is_cashier = auth.role == Role.CASHIER
    return service.build_overview(
        db,
        auth.organization,
        cashier_id=auth.user.id if is_cashier else None,
        include_costs=can_see_costs(auth),
    )
