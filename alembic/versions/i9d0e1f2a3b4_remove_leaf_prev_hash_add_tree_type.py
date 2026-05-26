"""remove leaf_hash/prev_hash, split tree_nodes into workflow_tree_nodes and session_tree_nodes

Revision ID: i9d0e1f2a3b4
Revises: h8c5d6e7f9a3
Create Date: 2026-05-27 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "h8c5d6e7f9a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("sessions", "leaf_hash")
    op.drop_column("sessions", "prev_hash")

    op.drop_column("events", "leaf_hash")
    op.drop_column("events", "prev_hash")

    op.rename_table("tree_nodes", "workflow_tree_nodes")
    op.alter_column("workflow_tree_nodes", "workflow_id", nullable=False)
    op.drop_index("ix_tree_nodes_session_id", table_name="workflow_tree_nodes")
    op.drop_index("ix_tree_nodes_workflow_id", table_name="workflow_tree_nodes")
    op.add_column("workflow_tree_nodes", sa.Column("entry", sa.String(length=64), nullable=True))
    op.create_index("ix_workflow_tree_nodes_workflow_id", "workflow_tree_nodes", ["workflow_id"], unique=False)

    op.create_table(
        "session_tree_nodes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("entry", sa.String(length=64), nullable=True),
        sa.Column("left_hash", sa.String(length=64), nullable=True),
        sa.Column("right_hash", sa.String(length=64), nullable=True),
        sa.Column("parent_hash", sa.String(length=64), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_leaf", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_tree_nodes_session_id", "session_tree_nodes", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_session_tree_nodes_session_id", table_name="session_tree_nodes")
    op.drop_table("session_tree_nodes")

    op.drop_index("ix_workflow_tree_nodes_workflow_id", table_name="workflow_tree_nodes")
    op.drop_column("workflow_tree_nodes", "entry")
    op.create_index("ix_tree_nodes_session_id", "workflow_tree_nodes", ["session_id"], unique=False)
    op.create_index("ix_tree_nodes_workflow_id", "workflow_tree_nodes", ["workflow_id"], unique=False)
    op.alter_column("workflow_tree_nodes", "workflow_id", nullable=True)
    op.rename_table("workflow_tree_nodes", "tree_nodes")

    op.add_column("sessions", sa.Column("leaf_hash", sa.String(length=64), nullable=False))
    op.add_column("sessions", sa.Column("prev_hash", sa.String(length=64), nullable=False))

    op.add_column("events", sa.Column("leaf_hash", sa.String(length=64), nullable=False))
    op.add_column("events", sa.Column("prev_hash", sa.String(length=64), nullable=False))
