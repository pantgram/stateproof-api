"""add user status and invite tokens

Revision ID: e0444576ba4d
Revises: be16cb1d8f5d
Create Date: 2026-05-25 20:54:32.742740

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

user_status = sa.Enum('pending', 'active', name='user_status', create_type=True)


# revision identifiers, used by Alembic.
revision: str = 'e0444576ba4d'
down_revision: Union[str, Sequence[str], None] = 'be16cb1d8f5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_status.create(op.get_bind(), checkfirst=True)
    op.create_table('invite_tokens',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('token', sa.String(length=128), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invite_tokens_token'), 'invite_tokens', ['token'], unique=True)
    op.add_column('users', sa.Column('status', user_status, server_default='active', nullable=False))
    op.drop_column('users', 'is_active')


def downgrade() -> None:
    op.add_column('users', sa.Column('is_active', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=False))
    op.drop_column('users', 'status')
    op.drop_index(op.f('ix_invite_tokens_token'), table_name='invite_tokens')
    op.drop_table('invite_tokens')
    user_status.drop(op.get_bind(), checkfirst=True)
