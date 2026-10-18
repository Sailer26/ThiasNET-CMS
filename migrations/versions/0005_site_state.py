"""stato condiviso del sito: generazione della cache delle pagine (Fase 3, D-54)

Revision ID: 0005_site_state
Revises: 0004_pages
Create Date: 2026-10-18
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0005_site_state"
down_revision = "0004_pages"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "site_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cache_generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_site_state_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_state")),
    )
    now = datetime.now(UTC).replace(tzinfo=None)  # le colonne salvano UTC senza fuso
    op.bulk_insert(table, [{"id": 1, "cache_generation": 0, "updated_at": now}])


def downgrade():
    op.drop_table("site_state")
