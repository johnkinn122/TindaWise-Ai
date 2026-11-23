from fastapi import APIRouter, Response, status

from app.api.deps import Auth, DbSession
from app.core.config import get_settings
from app.core.errors import ForbiddenError
from app.schemas.auth import LoginRequest, Me, SessionCreated, SignupRequest
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_response(context: service.AuthContext, token: str) -> SessionCreated:
    return SessionCreated(
        user=context.user,
        organization=context.organization,
        role=context.role.value,
        token=token,
        expires_at=context.session.expires_at,
    )


@router.post("/signup", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
def signup(data: SignupRequest, db: DbSession):
    """Create an account and a store, and sign in as its owner. Off on the public demo, so
    visitors aren't invited to leave a real email and password there."""
    if get_settings().demo_mode:
        raise ForbiddenError(
            "This is a public demo, so sign-up is turned off. Sign in with a demo account."
        )
    context, token = service.signup(db, data)
    return _session_response(context, token)


@router.post("/login", response_model=SessionCreated)
def login(data: LoginRequest, db: DbSession):
    context, token = service.login(db, data)
    return _session_response(context, token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth: Auth, db: DbSession) -> Response:
    service.logout(db, auth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=Me)
def me(auth: Auth):
    return Me(user=auth.user, organization=auth.organization, role=auth.role.value)
