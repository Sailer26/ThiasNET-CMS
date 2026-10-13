"""utenti, audit_log e login_attempts (Fase 1)

Revision ID: 0002_users_audit
Revises: 0001_baseline
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_users_audit"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("can_publish", sa.Boolean(), nullable=False),
        sa.Column("totp_secret_enc", sa.String(length=255), nullable=True),
        sa.Column("totp_last_counter", sa.Integer(), nullable=True),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("tour_completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'editor')", name=op.f("ck_users_role_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("diff_json", sa.JSON(), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_audit_log_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"])
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"])
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_key", sa.String(length=64), nullable=False),
        sa.Column("ip_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempts")),
    )
    op.create_index(op.f("ix_login_attempts_email_key"), "login_attempts", ["email_key"])
    op.create_index(op.f("ix_login_attempts_ip_key"), "login_attempts", ["ip_key"])
    op.create_index(op.f("ix_login_attempts_created_at"), "login_attempts", ["created_at"])


def downgrade():
    op.drop_table("login_attempts")
    op.drop_table("audit_log")
    op.drop_table("users")
