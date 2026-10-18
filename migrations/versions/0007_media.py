"""libreria media: file caricati e cartelle (Fase 4, D-70..D-85)

Revision ID: 0007_media
Revises: 0006_contact_messages
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_media"
down_revision = "0006_contact_messages"
branch_labels = None
depends_on = None

ROOT_FOLDER = sa.text("parent_id IS NULL")


def _user_fk(column):
    return sa.ForeignKeyConstraint(
        [column], ["users.id"], name=op.f(f"fk_media_{column}_users"), ondelete="SET NULL"
    )


def upgrade():
    op.create_table(
        "media_folders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_key", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["media_folders.id"],
            name=op.f("fk_media_folders_parent_id_media_folders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_folders")),
        sa.UniqueConstraint("parent_id", "name_key", name=op.f("uq_media_folders_parent_id")),
    )
    op.create_index(
        "uq_media_folders_root_name",
        "media_folders",
        ["name_key"],
        unique=True,
        sqlite_where=ROOT_FOLDER,
        postgresql_where=ROOT_FOLDER,
    )
    op.create_table(
        "media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("mime", sa.String(length=40), nullable=False),
        sa.Column("ext", sa.String(length=5), nullable=False),
        sa.Column("original_name", sa.String(length=200), nullable=False),
        sa.Column("search_key", sa.String(length=500), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt", sa.String(length=250), server_default=sa.text("''"), nullable=False),
        sa.Column("focal_x", sa.SmallInteger(), server_default="50", nullable=False),
        sa.Column("focal_y", sa.SmallInteger(), server_default="50", nullable=False),
        sa.Column("variants_json", sa.JSON(), nullable=False),
        sa.Column("file_rev", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('image', 'document')", name=op.f("ck_media_kind_valid")),
        sa.CheckConstraint(
            "focal_x BETWEEN 0 AND 100 AND focal_y BETWEEN 0 AND 100",
            name=op.f("ck_media_focal_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["folder_id"],
            ["media_folders.id"],
            name=op.f("fk_media_folder_id_media_folders"),
            ondelete="RESTRICT",
        ),
        _user_fk("created_by"),
        _user_fk("updated_by"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media")),
        sa.UniqueConstraint("sha256", name=op.f("uq_media_sha256")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_media_storage_key")),
    )
    op.create_index(op.f("ix_media_folder_id"), "media", ["folder_id"])
    op.create_index(op.f("ix_media_created_at"), "media", ["created_at"])


def downgrade():
    op.drop_table("media")
    op.drop_table("media_folders")
