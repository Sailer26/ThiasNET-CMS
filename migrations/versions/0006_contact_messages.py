"""messaggi del modulo contatti (Fase 3, D-05, D-61, D-67)

Revision ID: 0006_contact_messages
Revises: 0005_site_state
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_contact_messages"
down_revision = "0005_site_state"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("form_page_id", sa.Integer(), nullable=True),
        sa.Column("block_uid", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("send_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["form_page_id"],
            ["pages.id"],
            name=op.f("fk_contact_messages_form_page_id_pages"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_messages")),
    )
    op.create_index(
        "ix_contact_messages_ip_hash_created_at", "contact_messages", ["ip_hash", "created_at"]
    )
    op.create_index(op.f("ix_contact_messages_created_at"), "contact_messages", ["created_at"])
    op.create_index(op.f("ix_contact_messages_sent_at"), "contact_messages", ["sent_at"])


def downgrade():
    op.drop_table("contact_messages")
