from fastapi import APIRouter, status

from app.api.deps import CurrentOrg, DbSession
from app.schemas.category import CategoryCreate, CategoryRead
from app.services import products as service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
def list_categories(db: DbSession, org: CurrentOrg):
    return service.list_categories(db, org.id)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: DbSession, org: CurrentOrg):
    return service.create_category(db, org.id, data)
