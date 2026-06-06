"""remove workflow trees

Revision ID: m0a1b2c3d4e5
Revises: f5a6b7c8d9e0
Create Date: 2026-06-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("workflow_tree_nodes")
    op.drop_column("workflows", "hex_root")
    op.drop_column("workflows", "leaf_hashes")
    op.drop_column("workflows", "leaf_session_ids")


def downgrade() -> None:
    op.add_column("workflows", sa.Column("leaf_session_ids", sa.JSON(), server_default="[]", nullable=True))
    op.add_column("workflows", sa.Column("leaf_hashes", sa.JSON(), server_default="[]", nullable=True))
    op.add_column("workflows", sa.Column("hex_root", sa.String(64), server_default="0" * 64, nullable=False))
    op.create_table(
        "workflow_tree_nodes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("left_hash", sa.String(64), nullable=True),
        sa.Column("right_hash", sa.String(64), nullable=True),
        sa.Column("parent_hash", sa.String(64), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_leaf", sa.Boolean(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_tree_nodes_workflow_id", "workflow_tree_nodes", ["workflow_id"])
    op.create_index("ix_workflow_tree_nodes_workflow_id_level_position", "workflow_tree_nodes", ["workflow_id", "level", "position"])
    op.create_index("ix_workflow_tree_nodes_session_id_is_leaf", "workflow_tree_nodes", ["session_id"], postgresql_where=sa.text("is_leaf = true"))
