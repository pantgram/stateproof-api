"""add data_hash column to events

Revision ID: q4d5e6f7a8b9
Revises: p3b4c5d6e7f8
Create Date: 2026-06-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "p3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("data_hash", sa.String(64), nullable=False))
    op.create_index("ix_events_data_hash", "events", ["data_hash"])


def downgrade() -> None:
    op.drop_index("ix_events_data_hash", table_name="events")
    op.drop_column("events", "data_hash")
