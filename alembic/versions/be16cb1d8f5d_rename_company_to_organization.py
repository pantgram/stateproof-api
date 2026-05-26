"""rename company to organization

Revision ID: be16cb1d8f5d
Revises: d3754eb50c5b
Create Date: 2026-05-25 20:38:10.103920

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'be16cb1d8f5d'
down_revision: Union[str, Sequence[str], None] = 'd3754eb50c5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table('companies', 'organizations')

    op.drop_constraint(op.f('clients_company_id_fkey'), 'clients', type_='foreignkey')
    op.alter_column('clients', 'company_id', new_column_name='organization_id')
    op.create_foreign_key(None, 'clients', 'organizations', ['organization_id'], ['id'])

    op.drop_constraint(op.f('users_company_id_fkey'), 'users', type_='foreignkey')
    op.alter_column('users', 'company_id', new_column_name='organization_id')
    op.create_foreign_key(None, 'users', 'organizations', ['organization_id'], ['id'])

    op.drop_constraint(op.f('workflows_company_id_fkey'), 'workflows', type_='foreignkey')
    op.alter_column('workflows', 'company_id', new_column_name='organization_id')
    op.create_foreign_key(None, 'workflows', 'organizations', ['organization_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'workflows', type_='foreignkey')
    op.alter_column('workflows', 'organization_id', new_column_name='company_id')
    op.create_foreign_key(None, 'workflows', 'companies', ['company_id'], ['id'])

    op.drop_constraint(None, 'users', type_='foreignkey')
    op.alter_column('users', 'organization_id', new_column_name='company_id')
    op.create_foreign_key(None, 'users', 'companies', ['company_id'], ['id'])

    op.drop_constraint(None, 'clients', type_='foreignkey')
    op.alter_column('clients', 'organization_id', new_column_name='company_id')
    op.create_foreign_key(None, 'clients', 'companies', ['company_id'], ['id'])

    op.rename_table('organizations', 'companies')
