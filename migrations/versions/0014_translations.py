"""una traduzione per lingua in ogni gruppo (Fase 7c, D-151)

Revision ID: 0014_translations
Revises: 0013_entries
Create Date: 2026-10-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_translations"
down_revision = "0013_entries"
branch_labels = None
depends_on = None

LIVE = sa.text("deleted_at IS NULL")


def upgrade():
    for table in ("pages", "entries"):
        op.create_index(
            f"uq_{table}_group_locale",
            table,
            ["translation_group", "locale"],
            unique=True,
            sqlite_where=LIVE,
            postgresql_where=LIVE,
        )


def downgrade():
    op.drop_index("uq_entries_group_locale", table_name="entries")
    op.drop_index("uq_pages_group_locale", table_name="pages")
