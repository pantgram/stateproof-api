"""merge heads

Revision ID: d2899d3c2373
Revises: b2c3d4e5f6a7, l2a3b4c5d6e7
Create Date: 2026-05-28 11:50:12.059248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2899d3c2373'
down_revision: Union[str, Sequence[str], None] = ('b2c3d4e5f6a7', 'l2a3b4c5d6e7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
