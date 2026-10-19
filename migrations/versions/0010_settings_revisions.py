"""impostazioni dal pannello e versioni generiche (Fase 6a, D-139, D-143)

Revision ID: 0010_settings_revisions
Revises: 0009_support_requests
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_settings_revisions"
down_revision = "0009_support_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "settings",
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("values_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_settings_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("scope", name=op.f("pk_settings")),
    )
    op.create_table(
        "entity_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_key", sa.String(length=64), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_entity_revisions_author_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entity_revisions")),
    )
    op.create_index(
        "ix_entity_revisions_entity",
        "entity_revisions",
        ["entity_type", "entity_key", "created_at"],
    )


def downgrade():
    op.drop_index("ix_entity_revisions_entity", table_name="entity_revisions")
    op.drop_table("entity_revisions")
    op.drop_table("settings")
