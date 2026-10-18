"""stato condiviso del sito: generazione della cache delle pagine (Fase 3, D-54)

Revision ID: 0005_site_state
Revises: 0004_pages
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_site_state"
down_revision = "0004_pages"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cache_generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_site_state_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_state")),
    )
    op.execute(
        "INSERT INTO site_state (id, cache_generation, updated_at) VALUES (1, 0, CURRENT_TIMESTAMP)"
    )


def downgrade():
    op.drop_table("site_state")
