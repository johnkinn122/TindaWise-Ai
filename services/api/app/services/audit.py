"""The audit trail: `record` adds an event to the caller's transaction; `list_events` reads them.

`record` never commits. Each service calls it just before its own commit, so the change and its
audit event are saved together or not at all. Replays of an idempotent request return before
reaching `record`, so a retried refund or approval is logged once.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditAction, AuditEvent, Organization, User
from app.services.inventory_ledger import store_day_range


def money(amount: Decimal, currency: str) -> str:
    """₱1,234.50 for pesos, "USD 1,234.50" otherwise. Summaries are plain text, written once."""
    value = f"{amount:,.2f}"
    return f"₱{value}" if currency == "PHP" else f"{currency} {value}"


def record(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID | None,
    summary: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add an audit event to the session. The caller commits it with the change it describes.
    `details` must be JSON-ready (strings for money, ISO strings for dates)."""
    event = AuditEvent(
        organization_id=org_id,
        actor_user_id=actor_id,
        action=action.value,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary[:280],
        details=details or {},
    )
    db.add(event)
    return event


@dataclass(frozen=True)
class EventFilters:
    action: AuditAction | None = None
    actor_id: uuid.UUID | None = None
    start: date | None = None  # store day, included
    end: date | None = None  # store day, included


def list_events(
    db: Session, org: Organization, filters: EventFilters, *, limit: int, offset: int
) -> tuple[list[tuple[AuditEvent, str | None]], int]:
    """Newest first, with each actor's name. Returns (rows, total for these filters)."""
    conditions = [AuditEvent.organization_id == org.id]
    if filters.action:
        conditions.append(AuditEvent.action == filters.action.value)
    if filters.actor_id:
        conditions.append(AuditEvent.actor_user_id == filters.actor_id)
    since, until = store_day_range(org, filters.start, filters.end)
    if since:
        conditions.append(AuditEvent.created_at >= since)
    if until:
        conditions.append(AuditEvent.created_at < until)

    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*conditions)) or 0
    rows = db.execute(
        select(AuditEvent, User.full_name)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(*conditions)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [(event, name) for event, name in rows], total
