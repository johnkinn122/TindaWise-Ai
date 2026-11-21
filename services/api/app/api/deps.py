"""Request dependencies shared by every endpoint."""

import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotConfiguredError, NotFoundError
from app.db.session import get_db
from app.models import Organization

DbSession = Annotated[Session, Depends(get_db)]


def get_current_org(
    db: DbSession,
    x_organization_id: Annotated[uuid.UUID, Header(description="Development only")],
) -> Organization:
    """Resolve which organization this request acts for.

    TEMPORARY — authentication is not built yet. Until it is, development and tests pass the
    organization id in the `X-Organization-Id` header. That header is trivially spoofable, so in
    production this dependency refuses every request instead of trusting it. When auth lands,
    only this function changes: it will read the organization from the signed-in user's session.
    """
    if get_settings().environment == "production":
        raise NotConfiguredError("Authentication is not configured yet.")

    org = db.get(Organization, x_organization_id)
    if org is None:
        raise NotFoundError("Organization not found.")
    return org


CurrentOrg = Annotated[Organization, Depends(get_current_org)]
