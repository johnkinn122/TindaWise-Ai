"""Sign-up, sign-in, sessions and team membership."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthenticatedError
from app.core.security import (
    hash_password,
    hash_token,
    new_session_token,
    password_needs_rehash,
    verify_password,
)
from app.models import AuditAction, AuthSession, Membership, Organization, Role, User
from app.schemas.auth import LoginRequest, MemberCreate, SignupRequest
from app.services.audit import record

# Updating last_seen_at on every request would be a write per read; once in a while is enough.
_LAST_SEEN_RESOLUTION = timedelta(minutes=5)

INVALID_CREDENTIALS = "Email or password is incorrect."


@dataclass(frozen=True)
class AuthContext:
    """Who is making this request, for which organization, with which role."""

    session: AuthSession
    user: User
    organization: Organization
    role: Role

    def has_role(self, *roles: Role) -> bool:
        return self.role in roles


def _now() -> datetime:
    return datetime.now(UTC)


def _start_session(db: Session, user: User, organization_id: uuid.UUID) -> tuple[AuthSession, str]:
    token = new_session_token()
    session = AuthSession(
        token_hash=hash_token(token),
        user_id=user.id,
        organization_id=organization_id,
        expires_at=_now() + timedelta(days=get_settings().session_ttl_days),
    )
    db.add(session)
    return session, token


def signup(db: Session, data: SignupRequest) -> tuple[AuthContext, str]:
    """Create a person, their store, and make them its owner — all or nothing."""
    user = User(
        email=data.email, full_name=data.full_name, password_hash=hash_password(data.password)
    )
    organization = Organization(name=data.store_name, currency="PHP")
    db.add_all([user, organization])
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "An account with this email already exists. Sign in instead.",
            fields={"email": "Already has an account"},
        ) from exc
    db.add(Membership(user_id=user.id, organization_id=organization.id, role=Role.OWNER.value))
    session, token = _start_session(db, user, organization.id)
    db.commit()
    return AuthContext(session, user, organization, Role.OWNER), token


def login(db: Session, data: LoginRequest) -> tuple[AuthContext, str]:
    user = db.scalar(select(User).where(User.email == data.email))
    # verify_password runs even for unknown emails, so timing doesn't reveal which accounts exist.
    if not verify_password(user.password_hash if user else None, data.password) or user is None:
        raise UnauthenticatedError(INVALID_CREDENTIALS)
    if not user.is_active:
        raise UnauthenticatedError("This account is turned off. Ask your store owner.")

    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
    )
    if membership is None:
        raise UnauthenticatedError("This account isn't part of any store yet.")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(data.password)
    session, token = _start_session(db, user, membership.organization_id)
    db.commit()
    organization = db.get(Organization, membership.organization_id)
    assert organization is not None
    return AuthContext(session, user, organization, Role(membership.role)), token


def resolve_session(db: Session, token: str) -> AuthContext:
    """Turn a bearer token into an AuthContext, or refuse it."""
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    now = _now()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise UnauthenticatedError("Your session has ended. Sign in again.")

    user = db.get(User, session.user_id)
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == session.user_id,
            Membership.organization_id == session.organization_id,
        )
    )
    organization = db.get(Organization, session.organization_id)
    if user is None or not user.is_active or membership is None or organization is None:
        raise UnauthenticatedError("Your session has ended. Sign in again.")

    if now - session.last_seen_at > _LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        db.commit()
    return AuthContext(session, user, organization, Role(membership.role))


def logout(db: Session, context: AuthContext) -> None:
    context.session.revoked_at = _now()
    db.commit()


# ── Team ────────────────────────────────────────────────────────────────────


def list_members(db: Session, organization_id: uuid.UUID) -> list[tuple[Membership, User]]:
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == organization_id)
        .order_by(Membership.created_at)
    ).all()
    return [(membership, user) for membership, user in rows]


def add_member(
    db: Session, organization_id: uuid.UUID, data: MemberCreate, *, actor_id: uuid.UUID
) -> tuple[Membership, User]:
    """Create a new account directly in this store.

    An existing account is refused rather than attached: adding someone else's account to your
    store without their consent would be a takeover. Invitations by email can come later.
    """
    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.temporary_password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Someone already has an account with this email.",
            fields={"email": "Already has an account"},
        ) from exc
    membership = Membership(user_id=user.id, organization_id=organization_id, role=data.role)
    db.add(membership)
    record(
        db,
        org_id=organization_id,
        actor_id=actor_id,
        action=AuditAction.MEMBER_ADDED,
        entity_type="user",
        entity_id=user.id,
        summary=f"Added {user.full_name} ({user.email}) as {data.role}",
        details={"email": user.email, "role": str(data.role)},
    )
    db.commit()
    return membership, user
