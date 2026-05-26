"""widen client api_key column

Revision ID: d7a2c3e8f5b1
Revises: c4f1a8200101
Create Date: 2026-05-25 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd7a2c3e8f5b1'
down_revision: Union[str, Sequence[str], None] = 'c4f1a8200101'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('clients', 'api_key',
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column('clients', 'api_key',
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
