"""richieste "Chiedi a Thias" (Fase 5d-1, D-134)

Revision ID: 0009_support_requests
Revises: 0008_messages_read_audit
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_support_requests"
down_revision = "0008_messages_read_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("page_id", sa.Integer(), nullable=True),
        sa.Column("screen", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("send_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_support_requests_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["pages.id"],
            name=op.f("fk_support_requests_page_id_pages"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_requests")),
    )
    op.create_index(op.f("ix_support_requests_created_at"), "support_requests", ["created_at"])
    op.create_index(op.f("ix_support_requests_sent_at"), "support_requests", ["sent_at"])
    op.create_index(
        "ix_support_requests_user_id_created_at", "support_requests", ["user_id", "created_at"]
    )


def downgrade():
    op.drop_index("ix_support_requests_user_id_created_at", table_name="support_requests")
    op.drop_index(op.f("ix_support_requests_sent_at"), table_name="support_requests")
    op.drop_index(op.f("ix_support_requests_created_at"), table_name="support_requests")
    op.drop_table("support_requests")
