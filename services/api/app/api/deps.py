"""Request dependencies shared by every endpoint."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthenticatedError
from app.db.session import get_db
from app.models import Organization, Role
from app.services.auth import AuthContext, resolve_session

DbSession = Annotated[Session, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False, description="Session token from /api/v1/auth/login")


def get_auth(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthContext:
    """Every protected endpoint starts here: no valid session, no access."""
    if credentials is None or not credentials.credentials:
        raise UnauthenticatedError("Sign in to continue.")
    return resolve_session(db, credentials.credentials)


Auth = Annotated[AuthContext, Depends(get_auth)]


def get_current_org(auth: Auth) -> Organization:
    """The organization comes from the signed-in session, never from the request."""
    return auth.organization


CurrentOrg = Annotated[Organization, Depends(get_current_org)]


def require_roles(*roles: Role) -> Callable[[AuthContext], AuthContext]:
    """Dependency factory: allow only these roles. Checked on the server for every request."""

    def check(auth: Auth) -> AuthContext:
        if not auth.has_role(*roles):
            raise ForbiddenError("Your role doesn't allow this. Ask your store owner.")
        return auth

    return check


# Reusable permission levels.
CanManageInventory = Annotated[AuthContext, Depends(require_roles(Role.OWNER, Role.MANAGER))]
CanManageTeam = Annotated[AuthContext, Depends(require_roles(Role.OWNER))]
