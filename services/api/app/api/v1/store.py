from fastapi import APIRouter

from app.api.deps import CanEditStore, CanManageInventory, DbSession
from app.schemas.store import StoreRead, StoreUpdate
from app.services import store as service

router = APIRouter(prefix="/store", tags=["store"])


@router.get("", response_model=StoreRead)
def read_store(auth: CanManageInventory):
    """Owners and managers. Cashiers don't need the settings."""
    return auth.organization


@router.patch("", response_model=StoreRead)
def update_store(data: StoreUpdate, auth: CanEditStore, db: DbSession):
    """Owner only. The store is always the signed-in person's own: it comes from the session."""
    org = db.merge(auth.organization)
    return service.update_store(db, org, data)
