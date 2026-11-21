from fastapi import APIRouter, status

from app.api.deps import CanManageTeam, DbSession
from app.schemas.auth import MemberCreate, MemberRead
from app.services import auth as service

router = APIRouter(prefix="/members", tags=["team"])


def _read(membership, user) -> MemberRead:
    return MemberRead(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=membership.role,
        is_active=user.is_active,
        joined_at=membership.created_at,
    )


@router.get("", response_model=list[MemberRead])
def list_members(auth: CanManageTeam, db: DbSession):
    return [_read(m, u) for m, u in service.list_members(db, auth.organization.id)]


@router.post("", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def add_member(data: MemberCreate, auth: CanManageTeam, db: DbSession):
    """Owner adds a manager or cashier with a temporary password to share with them."""
    membership, user = service.add_member(db, auth.organization.id, data)
    return _read(membership, user)
