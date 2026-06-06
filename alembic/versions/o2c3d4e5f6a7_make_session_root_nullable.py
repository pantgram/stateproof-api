"""make session_root nullable for open sessions

Revision ID: o2c3d4e5f6a7
Revises: n1b2c3d4e5f6
Create Date: 2026-06-06 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "n1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("sessions", "session_root", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM sessions WHERE session_root IS NULL")
    op.alter_column("sessions", "session_root", nullable=False)
