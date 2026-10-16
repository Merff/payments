"""add payments webhook_sent_at

Revision ID: f08402433698
Revises: 8aaeb2369d79
Create Date: 2026-10-16 13:04:00.329567
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f08402433698"
down_revision: str | Sequence[str] | None = "8aaeb2369d79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("webhook_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "webhook_sent_at")
