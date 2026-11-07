"""add experiment reproducibility manifest

Revision ID: 69ab021eb7f8
Revises: 670639efd41a
Create Date: 2026-10-28 16:17:51.711046

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "69ab021eb7f8"
down_revision: str | Sequence[str] | None = "670639efd41a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column(
            "manifest",
            postgresql.JSONB(),
            nullable=True,
        ),
        schema="eval",
    )


def downgrade() -> None:
    op.drop_column(
        "experiments",
        "manifest",
        schema="eval",
    )
