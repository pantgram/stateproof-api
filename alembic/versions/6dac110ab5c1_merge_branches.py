"""merge branches

Revision ID: 6dac110ab5c1
Revises: e0444576ba4d, f1a2b3c4d5e6
Create Date: 2026-05-25 23:27:10.122217

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6dac110ab5c1'
down_revision: Union[str, Sequence[str], None] = ('e0444576ba4d', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
