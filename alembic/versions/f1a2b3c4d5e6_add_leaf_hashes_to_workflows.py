"""add leaf_hashes and leaf_session_ids to workflows

Revision ID: f1a2b3c4d5e6
Revises: d7a2c3e8f5b1
Create Date: 2026-05-25 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'd7a2c3e8f5b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workflows', sa.Column('leaf_hashes', postgresql.JSONB(), server_default='[]', nullable=False))
    op.add_column('workflows', sa.Column('leaf_session_ids', postgresql.JSONB(), server_default='[]', nullable=False))


def downgrade() -> None:
    op.drop_column('workflows', 'leaf_session_ids')
    op.drop_column('workflows', 'leaf_hashes')
