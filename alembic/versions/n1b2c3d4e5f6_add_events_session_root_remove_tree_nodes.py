"""add events table, session_root, remove tree nodes and session chaining

Revision ID: n1b2c3d4e5f6
Revises: m0a1b2c3d4e5
Create Date: 2026-06-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "m0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("session_root", sa.String(64), nullable=True))
    op.execute("UPDATE sessions SET session_root = session_hash")
    op.alter_column("sessions", "session_root", nullable=False)

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_session_id", "events", ["session_id"])
    op.create_index("ix_events_session_id_sequence_no", "events", ["session_id", "sequence_no"], unique=True)

    op.drop_table("session_tree_nodes")
    op.drop_column("sessions", "session_hash")
    op.drop_column("sessions", "leaf_hash")
    op.drop_column("sessions", "prev_hash")


def downgrade() -> None:
    op.add_column("sessions", sa.Column("prev_hash", sa.String(64), nullable=True))
    op.add_column("sessions", sa.Column("leaf_hash", sa.String(64), nullable=True))
    op.add_column("sessions", sa.Column("session_hash", sa.String(64), nullable=True))
    op.execute("UPDATE sessions SET session_hash = session_root")
    op.alter_column("sessions", "session_hash", nullable=False)
    op.alter_column("sessions", "leaf_hash", nullable=False)
    op.alter_column("sessions", "prev_hash", nullable=False)

    op.create_table(
        "session_tree_nodes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("left_hash", sa.String(64), nullable=True),
        sa.Column("right_hash", sa.String(64), nullable=True),
        sa.Column("parent_hash", sa.String(64), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_leaf", sa.Boolean(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_tree_nodes_session_id", "session_tree_nodes", ["session_id"])
    op.create_index("ix_session_tree_nodes_session_id_level_position", "session_tree_nodes", ["session_id", "level", "position"])
    op.create_index("ix_session_tree_nodes_session_id_is_leaf", "session_tree_nodes", ["session_id"], postgresql_where=sa.text("is_leaf = true"))

    op.drop_index("ix_events_session_id_sequence_no", table_name="events")
    op.drop_index("ix_events_session_id", table_name="events")
    op.drop_table("events")
    op.drop_column("sessions", "session_root")
