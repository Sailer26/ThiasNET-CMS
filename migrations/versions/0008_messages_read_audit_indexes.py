"""messaggi letti/da leggere e indici del registro (Fase 5c-2, D-124, D-126)

Revision ID: 0008_messages_read_audit
Revises: 0007_media
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_messages_read_audit"
down_revision = "0007_media"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contact_messages") as batch:
        batch.add_column(sa.Column("read_at", sa.DateTime(), nullable=True))
        batch.create_index(batch.f("ix_contact_messages_read_at"), ["read_at"])
    op.create_index("ix_audit_log_action_created_at", "audit_log", ["action", "created_at"])
    op.create_index("ix_audit_log_entity_entity_id", "audit_log", ["entity", "entity_id"])


def downgrade():
    op.drop_index("ix_audit_log_entity_entity_id", table_name="audit_log")
    op.drop_index("ix_audit_log_action_created_at", table_name="audit_log")
    with op.batch_alter_table("contact_messages") as batch:
        batch.drop_index(batch.f("ix_contact_messages_read_at"))
        batch.drop_column("read_at")
