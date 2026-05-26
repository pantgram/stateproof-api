"""remove session_count from workflows

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("workflows", "session_count")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("workflows", sa.Column("session_count", sa.Integer(), server_default="0", nullable=False))
