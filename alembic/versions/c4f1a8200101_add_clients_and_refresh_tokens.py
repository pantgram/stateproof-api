"""add clients and refresh_tokens

Revision ID: c4f1a8200101
Revises: b3a83d900893
Create Date: 2026-05-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4f1a8200101'
down_revision: Union[str, Sequence[str], None] = 'b3a83d900893'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('clients',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('api_key', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('api_key'),
    )
    op.create_index('ix_clients_api_key', 'clients', ['api_key'], unique=True)

    op.create_table('refresh_tokens',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('client_id', sa.Uuid(), nullable=False),
        sa.Column('token', sa.String(length=512), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index('ix_refresh_tokens_token', 'refresh_tokens', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_refresh_tokens_token', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index('ix_clients_api_key', table_name='clients')
    op.drop_table('clients')
