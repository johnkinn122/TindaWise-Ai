"""shrinkage dismissals

Revision ID: 0034c5890f56
Revises: 5f56d7cc7f53
Create Date: 2026-11-23 10:49:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0034c5890f56'
down_revision: str | Sequence[str] | None = '5f56d7cc7f53'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_anomaly_dismissals_kind_valid"


def upgrade() -> None:
    """Allow "shrinkage" (stock going missing) as a dismissal kind; it needs a wider column."""
    op.alter_column(
        "anomaly_dismissals", "kind", type_=sa.String(length=16), existing_nullable=False
    )
    op.drop_constraint(op.f(CONSTRAINT), "anomaly_dismissals", type_="check")
    op.create_check_constraint(
        "kind_valid", "anomaly_dismissals", "kind IN ('spike', 'drop', 'shrinkage')"
    )


def downgrade() -> None:
    """Shrinkage dismissals can't be kept in the old shape, so they are removed."""
    op.execute("DELETE FROM anomaly_dismissals WHERE kind = 'shrinkage'")
    op.drop_constraint(op.f(CONSTRAINT), "anomaly_dismissals", type_="check")
    op.create_check_constraint("kind_valid", "anomaly_dismissals", "kind IN ('spike', 'drop')")
    op.alter_column(
        "anomaly_dismissals", "kind", type_=sa.String(length=8), existing_nullable=False
    )
