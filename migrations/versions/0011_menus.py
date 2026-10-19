"""menu fatti a mano (Fase 6b, D-141, D-145)

Revision ID: 0011_menus
Revises: 0010_settings_revisions
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_menus"
down_revision = "0010_settings_revisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "menus",
        sa.Column("location", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_menus_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("location", "locale", name=op.f("pk_menus")),
    )


def downgrade():
    op.drop_table("menus")
