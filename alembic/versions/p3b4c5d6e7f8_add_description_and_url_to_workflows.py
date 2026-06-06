"""add description and url to workflows

Revision ID: p3b4c5d6e7f8
Revises: o2c3d4e5f6a7
Create Date: 2026-06-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "o2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("description", sa.String(1000), nullable=True))
    op.add_column("workflows", sa.Column("url", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("workflows", "url")
    op.drop_column("workflows", "description")
