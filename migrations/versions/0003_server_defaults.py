"""server_default per le colonne NOT NULL di users (rimando della review Fase 1)

Revision ID: 0003_server_defaults
Revises: 0002_users_audit
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_server_defaults"
down_revision = "0002_users_audit"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.alter_column("active", existing_type=sa.Boolean(), server_default=sa.true())
        batch.alter_column("can_publish", existing_type=sa.Boolean(), server_default=sa.false())
        batch.alter_column("session_version", existing_type=sa.Integer(), server_default="1")


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.alter_column("session_version", existing_type=sa.Integer(), server_default=None)
        batch.alter_column("can_publish", existing_type=sa.Boolean(), server_default=None)
        batch.alter_column("active", existing_type=sa.Boolean(), server_default=None)
