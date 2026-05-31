"""split tree nodes, remove events, update session model

Revision ID: k1f2a3b4c5d6
Revises: i9d0e1f2a3b4
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "k1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "i9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- sessions: add new columns ---
    op.add_column("sessions", sa.Column("leaf_hash", sa.String(64), nullable=True))
    op.add_column("sessions", sa.Column("prev_hash", sa.String(64), nullable=True))
    op.add_column("sessions", sa.Column("event_count", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("sessions", sa.Column("meta", JSONB, nullable=True))

    # --- session_tree_nodes: drop event_id + entry, add sequence_no, update indexes ---
    op.drop_constraint("session_tree_nodes_event_id_fkey", "session_tree_nodes", type_="foreignkey")
    op.drop_column("session_tree_nodes", "event_id")

    # --- drop events table ---
    op.drop_index("ix_events_session_id", table_name="events")
    op.drop_table("events")
    op.drop_column("session_tree_nodes", "entry")
    op.add_column("session_tree_nodes", sa.Column("sequence_no", sa.Integer(), nullable=True))

    op.drop_index("ix_session_tree_nodes_session_id", table_name="session_tree_nodes")
    op.create_index("ix_session_tree_nodes_session_id", "session_tree_nodes", ["session_id"])
    op.create_index(
        "ix_session_tree_nodes_session_id_level_position",
        "session_tree_nodes",
        ["session_id", "level", "position"],
    )
    op.execute(
        "CREATE INDEX ix_session_tree_nodes_session_id_is_leaf "
        "ON session_tree_nodes (session_id) WHERE is_leaf = true"
    )

    # --- workflow_tree_nodes: drop entry, update indexes ---
    op.drop_column("workflow_tree_nodes", "entry")

    op.drop_index("ix_workflow_tree_nodes_workflow_id", table_name="workflow_tree_nodes")
    op.create_index("ix_workflow_tree_nodes_workflow_id", "workflow_tree_nodes", ["workflow_id"])
    op.create_index(
        "ix_workflow_tree_nodes_workflow_id_level_position",
        "workflow_tree_nodes",
        ["workflow_id", "level", "position"],
    )
    op.execute(
        "CREATE INDEX ix_workflow_tree_nodes_session_id_is_leaf "
        "ON workflow_tree_nodes (session_id) WHERE is_leaf = true"
    )


def downgrade() -> None:
    # --- workflow_tree_nodes: restore entry, revert indexes ---
    op.execute("DROP INDEX IF EXISTS ix_workflow_tree_nodes_session_id_is_leaf")
    op.drop_index("ix_workflow_tree_nodes_workflow_id_level_position", table_name="workflow_tree_nodes")
    op.drop_index("ix_workflow_tree_nodes_workflow_id", table_name="workflow_tree_nodes")
    op.create_index("ix_workflow_tree_nodes_workflow_id", "workflow_tree_nodes", ["workflow_id"])
    op.add_column("workflow_tree_nodes", sa.Column("entry", sa.String(64), nullable=True))

    # --- session_tree_nodes: restore event_id + entry, drop sequence_no, revert indexes ---
    op.execute("DROP INDEX IF EXISTS ix_session_tree_nodes_session_id_is_leaf")
    op.drop_index("ix_session_tree_nodes_session_id_level_position", table_name="session_tree_nodes")
    op.drop_index("ix_session_tree_nodes_session_id", table_name="session_tree_nodes")
    op.create_index("ix_session_tree_nodes_session_id", "session_tree_nodes", ["session_id"])
    op.drop_column("session_tree_nodes", "sequence_no")
    op.add_column("session_tree_nodes", sa.Column("entry", sa.String(64), nullable=True))
    op.add_column(
        "session_tree_nodes",
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=True),
    )

    # --- recreate events table ---
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
    )
    op.create_index("ix_events_session_id", "events", ["session_id"])

    # --- sessions: drop new columns ---
    op.drop_column("sessions", "meta")
    op.drop_column("sessions", "event_count")
    op.drop_column("sessions", "prev_hash")
    op.drop_column("sessions", "leaf_hash")
