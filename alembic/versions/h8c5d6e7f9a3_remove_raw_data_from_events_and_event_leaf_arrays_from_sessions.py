"""remove raw data fields from events and event_leaf arrays and meta from sessions

Revision ID: h8c5d6e7f9a3
Revises: g7b4c5d6e8f2
Create Date: 2026-05-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8c5d6e7f9a3"
down_revision: Union[str, Sequence[str], None] = "g7b4c5d6e8f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("events", "data")
    op.drop_column("events", "timestamp")
    op.drop_column("events", "action")
    op.drop_column("events", "executor_type")
    op.drop_column("events", "event_type")

    op.drop_column("sessions", "event_leaf_ids")
    op.drop_column("sessions", "event_leaf_hashes")
    op.drop_column("sessions", "meta")


def downgrade() -> None:
    op.add_column(
        "events",
        sa.Column("event_type", sa.String(50), nullable=False),
    )
    op.add_column(
        "events",
        sa.Column("executor_type", sa.String(50), nullable=False),
    )
    op.add_column(
        "events",
        sa.Column("action", sa.String(255), nullable=False),
    )
    op.add_column(
        "events",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "events",
        sa.Column("data", sa.dialects.postgresql.JSONB, nullable=True),
    )

    op.add_column(
        "sessions",
        sa.Column("event_leaf_hashes", sa.dialects.postgresql.JSONB, server_default="[]", nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("event_leaf_ids", sa.dialects.postgresql.JSONB, server_default="[]", nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("meta", sa.dialects.postgresql.JSONB, nullable=True),
    )
