"""add cascade deletes to foreign keys

Revision ID: a1b2c3d4e5f6
Revises: 6dac110ab5c1
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "6dac110ab5c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("workflows_organization_id_fkey", "workflows", type_="foreignkey")
    op.create_foreign_key("workflows_organization_id_fkey", "workflows", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("sessions_workflow_id_fkey", "sessions", type_="foreignkey")
    op.create_foreign_key("sessions_workflow_id_fkey", "sessions", "workflows", ["workflow_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("tree_nodes_workflow_id_fkey", "tree_nodes", type_="foreignkey")
    op.create_foreign_key("tree_nodes_workflow_id_fkey", "tree_nodes", "workflows", ["workflow_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("tree_nodes_session_id_fkey", "tree_nodes", type_="foreignkey")
    op.create_foreign_key("tree_nodes_session_id_fkey", "tree_nodes", "sessions", ["session_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("users_organization_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key("users_organization_id_fkey", "users", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("clients_organization_id_fkey", "clients", type_="foreignkey")
    op.create_foreign_key("clients_organization_id_fkey", "clients", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("client_refresh_tokens_client_id_fkey", "client_refresh_tokens", type_="foreignkey")
    op.create_foreign_key("client_refresh_tokens_client_id_fkey", "client_refresh_tokens", "clients", ["client_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("user_refresh_tokens_user_id_fkey", "user_refresh_tokens", type_="foreignkey")
    op.create_foreign_key("user_refresh_tokens_user_id_fkey", "user_refresh_tokens", "users", ["user_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("invite_tokens_user_id_fkey", "invite_tokens", type_="foreignkey")
    op.create_foreign_key("invite_tokens_user_id_fkey", "invite_tokens", "users", ["user_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("invite_tokens_organization_id_fkey", "invite_tokens", type_="foreignkey")
    op.create_foreign_key("invite_tokens_organization_id_fkey", "invite_tokens", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("workflows_organization_id_fkey", "workflows", type_="foreignkey")
    op.create_foreign_key("workflows_organization_id_fkey", "workflows", "organizations", ["organization_id"], ["id"])

    op.drop_constraint("sessions_workflow_id_fkey", "sessions", type_="foreignkey")
    op.create_foreign_key("sessions_workflow_id_fkey", "sessions", "workflows", ["workflow_id"], ["id"])

    op.drop_constraint("tree_nodes_workflow_id_fkey", "tree_nodes", type_="foreignkey")
    op.create_foreign_key("tree_nodes_workflow_id_fkey", "tree_nodes", "workflows", ["workflow_id"], ["id"])

    op.drop_constraint("tree_nodes_session_id_fkey", "tree_nodes", type_="foreignkey")
    op.create_foreign_key("tree_nodes_session_id_fkey", "tree_nodes", "sessions", ["session_id"], ["id"])

    op.drop_constraint("users_organization_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key("users_organization_id_fkey", "users", "organizations", ["organization_id"], ["id"])

    op.drop_constraint("clients_organization_id_fkey", "clients", type_="foreignkey")
    op.create_foreign_key("clients_organization_id_fkey", "clients", "organizations", ["organization_id"], ["id"])

    op.drop_constraint("client_refresh_tokens_client_id_fkey", "client_refresh_tokens", type_="foreignkey")
    op.create_foreign_key("client_refresh_tokens_client_id_fkey", "client_refresh_tokens", "clients", ["client_id"], ["id"])

    op.drop_constraint("user_refresh_tokens_user_id_fkey", "user_refresh_tokens", type_="foreignkey")
    op.create_foreign_key("user_refresh_tokens_user_id_fkey", "user_refresh_tokens", "users", ["user_id"], ["id"])

    op.drop_constraint("invite_tokens_user_id_fkey", "invite_tokens", type_="foreignkey")
    op.create_foreign_key("invite_tokens_user_id_fkey", "invite_tokens", "users", ["user_id"], ["id"])

    op.drop_constraint("invite_tokens_organization_id_fkey", "invite_tokens", type_="foreignkey")
    op.create_foreign_key("invite_tokens_organization_id_fkey", "invite_tokens", "organizations", ["organization_id"], ["id"])
