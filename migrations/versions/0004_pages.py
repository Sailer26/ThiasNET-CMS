"""pagine, blocchi, revisioni, bozze e reindirizzamenti (Fase 2)

Revision ID: 0004_pages
Revises: 0003_server_defaults
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_pages"
down_revision = "0003_server_defaults"
branch_labels = None
depends_on = None

BLOCK_TYPES = (
    "contacts", "cta", "divider", "files", "gallery", "heading", "hero",
    "image", "map", "quote", "text", "text_image", "video",
)
LIVE = sa.text("deleted_at IS NULL")
SCHEDULED = sa.text("kind = 'scheduled'")


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _user_fk(table, column):
    return sa.ForeignKeyConstraint(
        [column], ["users.id"], name=op.f(f"fk_{table}_{column}_users"), ondelete="SET NULL"
    )


def _page_fk(table):
    return sa.ForeignKeyConstraint(
        ["page_id"], ["pages.id"], name=op.f(f"fk_{table}_page_id_pages"), ondelete="CASCADE"
    )


def upgrade():
    op.create_table(
        "pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("translation_group", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("layout", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("publish_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("seo_json", sa.JSON(), nullable=False),
        sa.Column("sort", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            _in("status", ("draft", "published", "scheduled")),
            name=op.f("ck_pages_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["pages.id"], name=op.f("fk_pages_parent_id_pages"), ondelete="RESTRICT"
        ),
        _user_fk("pages", "created_by"),
        _user_fk("pages", "updated_by"),
        _user_fk("pages", "deleted_by"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pages")),
    )
    op.create_index(op.f("ix_pages_parent_id"), "pages", ["parent_id"])
    op.create_index(op.f("ix_pages_translation_group"), "pages", ["translation_group"])
    op.create_index("ix_pages_status_publish_at", "pages", ["status", "publish_at"])
    op.create_index(
        "uq_pages_locale_path",
        "pages",
        ["locale", "path"],
        unique=True,
        sqlite_where=LIVE,
        postgresql_where=LIVE,
    )

    op.create_table(
        "blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.String(length=32), nullable=False),
        sa.Column("zone", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("variant", sa.String(length=64), nullable=True),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.CheckConstraint(_in("type", BLOCK_TYPES), name=op.f("ck_blocks_type_valid")),
        _page_fk("blocks"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blocks")),
        sa.UniqueConstraint("page_id", "uid", name=op.f("uq_blocks_page_id")),
    )
    op.create_index("ix_blocks_page_id_zone_sort", "blocks", ["page_id", "zone", "sort"])

    op.create_table(
        "page_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            _in("kind", ("published", "scheduled", "unpublished", "draft")),
            name=op.f("ck_page_revisions_kind_valid"),
        ),
        _page_fk("page_revisions"),
        _user_fk("page_revisions", "author_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_revisions")),
    )
    op.create_index(
        "ix_page_revisions_page_id_created_at", "page_revisions", ["page_id", "created_at"]
    )
    op.create_index(
        "uq_page_revisions_scheduled",
        "page_revisions",
        ["page_id"],
        unique=True,
        sqlite_where=SCHEDULED,
        postgresql_where=SCHEDULED,
    )

    op.create_table(
        "page_drafts",
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        _page_fk("page_drafts"),
        _user_fk("page_drafts", "author_id"),
        sa.PrimaryKeyConstraint("page_id", name=op.f("pk_page_drafts")),
    )

    op.create_table(
        "page_redirects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("from_path", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        _page_fk("page_redirects"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_redirects")),
        sa.UniqueConstraint("locale", "from_path", name=op.f("uq_page_redirects_locale")),
    )
    op.create_index(op.f("ix_page_redirects_page_id"), "page_redirects", ["page_id"])


def downgrade():
    op.drop_table("page_redirects")
    op.drop_table("page_drafts")
    op.drop_table("page_revisions")
    op.drop_table("blocks")
    op.drop_table("pages")
