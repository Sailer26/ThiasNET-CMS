"""voci delle raccolte e loro bozze (Fase 7a, D-147)

Revision ID: 0013_entries
Revises: 0012_widget_areas
Create Date: 2026-10-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_entries"
down_revision = "0012_widget_areas"
branch_labels = None
depends_on = None

LIVE = sa.text("deleted_at IS NULL")


def _user_fk(table, column):
    return sa.ForeignKeyConstraint(
        [column], ["users.id"], name=op.f(f"fk_{table}_{column}_users"), ondelete="SET NULL"
    )


def upgrade():
    op.create_table(
        "entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collection", sa.String(length=64), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("translation_group", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("seo_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("publish_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("sort_at", sa.DateTime(), nullable=True),
        sa.Column("scheduled_json", sa.JSON(), nullable=True),
        sa.Column("scheduled_by", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'scheduled')", name=op.f("ck_entries_status_valid")
        ),
        _user_fk("entries", "scheduled_by"),
        _user_fk("entries", "created_by"),
        _user_fk("entries", "updated_by"),
        _user_fk("entries", "deleted_by"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entries")),
    )
    op.create_index(op.f("ix_entries_translation_group"), "entries", ["translation_group"])
    op.create_index("ix_entries_listing", "entries", ["collection", "locale", "status", "sort_at"])
    op.create_index("ix_entries_publish_at", "entries", ["publish_at"])
    op.create_index(
        "uq_entries_locale_collection_slug",
        "entries",
        ["locale", "collection", "slug"],
        unique=True,
        sqlite_where=LIVE,
        postgresql_where=LIVE,
    )
    op.create_table(
        "entry_drafts",
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["entries.id"],
            name=op.f("fk_entry_drafts_entry_id_entries"),
            ondelete="CASCADE",
        ),
        _user_fk("entry_drafts", "author_id"),
        sa.PrimaryKeyConstraint("entry_id", name=op.f("pk_entry_drafts")),
    )


def downgrade():
    op.drop_table("entry_drafts")
    op.drop_index("uq_entries_locale_collection_slug", table_name="entries")
    op.drop_index("ix_entries_publish_at", table_name="entries")
    op.drop_index("ix_entries_listing", table_name="entries")
    op.drop_index(op.f("ix_entries_translation_group"), table_name="entries")
    op.drop_table("entries")
