"""add events table and event tree fields to sessions

Revision ID: g7b4c5d6e8f2
Revises: 6dac110ab5c1
Create Date: 2026-05-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "g7b4c5d6e8f2"
down_revision: Union[str, Sequence[str], None] = "6dac110ab5c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("event_leaf_hashes", JSONB, server_default="[]", nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("event_leaf_ids", JSONB, server_default="[]", nullable=True),
    )
    op.drop_column("sessions", "events")

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("session_id", sa.Uuid, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("leaf_hash", sa.String(64), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("sequence_no", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("executor_type", sa.String(50), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", JSONB, nullable=True),
    )
    op.create_index("ix_events_session_id", "events", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_events_session_id", table_name="events")
    op.drop_table("events")

    op.add_column(
        "sessions",
        sa.Column("events", JSONB, nullable=True),
    )
    op.drop_column("sessions", "event_leaf_hashes")
    op.drop_column("sessions", "event_leaf_ids")
