
# ─────────────────────────────────────────────────────────────────────────────
# alembic/versions/0004_add_analytics_indexes.py
# Performance indexes for the analytics queries above.
# ─────────────────────────────────────────────────────────────────────────────
"""
Revision ID: 0004
Revises: 0003
"""
from alembic import op

revision      = "0004"
down_revision = "0003"

def upgrade() -> None:
    # turns.created_at — used in every analytics WHERE clause
    op.create_index("ix_turns_created_at",    "turns",    ["created_at"])
    # turns.latency_ms — used for percentile calculation
    op.create_index("ix_turns_latency_ms",    "turns",    ["latency_ms"])
    # sessions.created_at — used in date bucketing
    op.create_index("ix_sessions_created_at", "sessions", ["created_at"])
    # feedback.turn_id + verdict — used for breakdown
    op.create_index("ix_feedback_turn_verdict","feedback", ["turn_id", "verdict"])
    op.create_index("ix_feedback_created_at",  "feedback", ["created_at"])

    # GIN index on turns.response JSONB so jsonb_array_elements is fast
    op.execute("""
        CREATE INDEX ix_turns_response_gin
        ON turns USING gin(response jsonb_path_ops)
    """)

def downgrade() -> None:
    for ix in [
        "ix_turns_created_at", "ix_turns_latency_ms",
        "ix_sessions_created_at", "ix_feedback_turn_verdict",
        "ix_feedback_created_at", "ix_turns_response_gin",
    ]:
        op.drop_index(ix, if_exists=True)
        