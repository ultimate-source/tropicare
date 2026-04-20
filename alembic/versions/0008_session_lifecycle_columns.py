# ─────────────────────────────────────────────────────────────────────────────
# alembic/versions/0008_session_lifecycle_columns.py
# Adds lifecycle columns (closed_at, updated_at, status) to the sessions table
# and creates indexes for efficient history queries.
# ─────────────────────────────────────────────────────────────────────────────
"""Add lifecycle columns to sessions table

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("sessions", sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True, server_default=sa.text("now()")))
    op.add_column("sessions", sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="active"))

    op.create_index("ix_sessions_user_created", "sessions", ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_sessions_status", "sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_index("ix_sessions_user_created", table_name="sessions")

    op.drop_column("sessions", "status")
    op.drop_column("sessions", "updated_at")
    op.drop_column("sessions", "closed_at")
