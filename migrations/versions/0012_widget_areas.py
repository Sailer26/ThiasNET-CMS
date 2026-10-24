"""aree widget (Fase 6c, D-142, D-146)

Revision ID: 0012_widget_areas
Revises: 0011_menus
Create Date: 2026-10-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_widget_areas"
down_revision = "0011_menus"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "widget_areas",
        sa.Column("area", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("next_change_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_widget_areas_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("area", "locale", name=op.f("pk_widget_areas")),
    )
    op.create_index(op.f("ix_widget_areas_next_change_at"), "widget_areas", ["next_change_at"])


def downgrade():
    op.drop_index(op.f("ix_widget_areas_next_change_at"), table_name="widget_areas")
    op.drop_table("widget_areas")
