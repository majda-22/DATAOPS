"""add experiment scenario evidence

Revision ID: 54787a59d5b3
Revises: 69ab021eb7f8
Create Date: 2026-11-07 19:10:13.723388

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "54787a59d5b3"
down_revision: str | Sequence[str] | None = "69ab021eb7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "experiment_scenarios",
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        schema="eval",
    )


def downgrade() -> None:
    op.drop_column(
        "experiment_scenarios",
        "evidence",
        schema="eval",
    )
