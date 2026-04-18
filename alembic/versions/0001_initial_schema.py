# ─────────────────────────────────────────────────────────────────────────────
# alembic/versions/0001_initial_schema.py
# ─────────────────────────────────────────────────────────────────────────────
"""Initial schema — all production tables

Revision ID: 0001
Revises:
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── Users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email",      sa.Text, nullable=False, unique=True),
        sa.Column("hashed_pw",  sa.Text, nullable=False),
        sa.Column("roles",      postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("active",     sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # ── Sessions ───────────────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id",         postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_context", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("language",        sa.VARCHAR(5), nullable=False, server_default="'fr'"),
        sa.Column("created_at",      sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at",      sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    # ── Turns ──────────────────────────────────────────────────────────────────
    op.create_table(
        "turns",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id",  postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("turn_index",  sa.Integer),
        sa.Column("query",       sa.Text, nullable=False),
        sa.Column("response",    postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("agent_trace", postgresql.JSONB),
        sa.Column("latency_ms",  sa.Integer),
        sa.Column("created_at",  sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_turns_session_id", "turns", ["session_id"])

    # ── KB Documents ───────────────────────────────────────────────────────────
    op.create_table(
        "kb_documents",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title",            sa.Text, nullable=False),
        sa.Column("source_url",       sa.Text),
        sa.Column("source_type",      sa.VARCHAR(50)),
        sa.Column("version",          sa.VARCHAR(50)),
        sa.Column("published_date",   sa.Date),
        sa.Column("ingested_at",      sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("superseded_by",    postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_documents.id")),
        sa.Column("language",         sa.VARCHAR(5)),
        sa.Column("disease_tags",     postgresql.ARRAY(sa.Text)),
        sa.Column("chunk_count",      sa.Integer, server_default="0"),
        sa.Column("raw_path",         sa.Text),
        sa.Column("ingestion_error",  sa.Text),
    )

    # ── KB Chunks (full-text index) ────────────────────────────────────────────
    op.create_table(
        "kb_chunks",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id",  postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_documents.id"), nullable=False),
        sa.Column("chunk_text",   sa.Text, nullable=False),
        sa.Column("section",      sa.Text),
        sa.Column("page",         sa.Integer),
        sa.Column("language",     sa.VARCHAR(5), server_default="'fr'"),
        sa.Column("disease_tags", postgresql.ARRAY(sa.Text)),
        sa.Column("drug_tags",    postgresql.ARRAY(sa.Text)),
        sa.Column("content_type", sa.VARCHAR(50), server_default="'guideline'"),
        sa.Column("content_hash", sa.VARCHAR(16), unique=True),
        sa.Column("token_count",  sa.Integer),
        sa.Column("superseded",   sa.Boolean, server_default="false"),
    )
    op.create_index("ix_kb_chunks_document_id", "kb_chunks", ["document_id"])
    op.create_index("ix_kb_chunks_content_hash", "kb_chunks", ["content_hash"])
    # Full-text search index (French + English)
    op.execute("""
        CREATE INDEX ix_kb_chunks_fts ON kb_chunks
        USING gin(to_tsvector('french', chunk_text))
    """)

    # ── CAME Formulary ─────────────────────────────────────────────────────────
    op.create_table(
        "came_formulary",
        sa.Column("id",           sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("generic_name", sa.Text, nullable=False),
        sa.Column("brand_names",  postgresql.ARRAY(sa.Text)),
        sa.Column("atc_code",     sa.VARCHAR(10)),
        sa.Column("available",    sa.Boolean, nullable=False, server_default="true"),
        sa.Column("dosage_forms", postgresql.ARRAY(sa.Text)),
        sa.Column("notes",        sa.Text),
        sa.Column("updated_at",   sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_came_formulary_generic", "came_formulary", [sa.text("lower(generic_name)")])

    # ── AMR Data ───────────────────────────────────────────────────────────────
    op.create_table(
        "amr_data",
        sa.Column("id",             sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("drug",           sa.Text, nullable=False),
        sa.Column("pathogen",       sa.Text, nullable=False),
        sa.Column("region",         sa.Text, nullable=False),
        sa.Column("resistance_pct", sa.Float),
        sa.Column("data_source",    sa.Text),
        sa.Column("year",           sa.Integer),
        sa.Column("confidence",     sa.VARCHAR(10)),  # high|medium|low|no_data
    )
    op.create_index("ix_amr_drug_pathogen", "amr_data", ["drug", "pathogen", "region"])

    # ── DDI Interactions ───────────────────────────────────────────────────────
    op.create_table(
        "ddi_interactions",
        sa.Column("id",              sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("drug_a",          sa.Text, nullable=False),
        sa.Column("drug_b",          sa.Text, nullable=False),
        sa.Column("severity",        sa.VARCHAR(20), nullable=False),
        sa.Column("mechanism",       sa.Text),
        sa.Column("clinical_effect", sa.Text),
        sa.Column("management",      sa.Text),
    )

    # ── Drug Safety (pregnancy) ────────────────────────────────────────────────
    op.create_table(
        "drug_safety",
        sa.Column("id",                  sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("drug",                sa.Text, nullable=False, unique=True),
        sa.Column("pregnancy_category",  sa.VARCHAR(5)),
        sa.Column("lactation_safe",      sa.Boolean),
        sa.Column("t1_notes",            sa.Text),
        sa.Column("t2_notes",            sa.Text),
        sa.Column("t3_notes",            sa.Text),
        sa.Column("source",              sa.Text),
    )

    # ── Audit Log (immutable, partitioned) ─────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id",         postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_type", sa.VARCHAR(100)),
        sa.Column("user_id",    postgresql.UUID(as_uuid=True)),
        sa.Column("session_id", postgresql.UUID(as_uuid=True)),
        sa.Column("turn_id",    postgresql.UUID(as_uuid=True)),
        sa.Column("payload",    postgresql.JSONB),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        postgresql_partition_by="RANGE (created_at)",
    )
    # Create first two year partitions
    op.execute("""
        CREATE TABLE audit_log_2026 PARTITION OF audit_log
        FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')
    """)
    op.execute("""
        CREATE TABLE audit_log_2027 PARTITION OF audit_log
        FOR VALUES FROM ('2027-01-01') TO ('2028-01-01')
    """)

    # ── Feedback ───────────────────────────────────────────────────────────────
    op.create_table(
        "feedback",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("turn_id",          postgresql.UUID(as_uuid=True)),
        sa.Column("user_id",          postgresql.UUID(as_uuid=True)),
        sa.Column("verdict",          sa.VARCHAR(20)),
        sa.Column("clinician_note",   sa.Text),
        sa.Column("actual_diagnosis", sa.Text),
        sa.Column("created_at",       sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    for tbl in [
        "feedback", "audit_log_2027", "audit_log_2026", "audit_log",
        "drug_safety", "ddi_interactions", "amr_data", "came_formulary",
        "kb_chunks", "kb_documents", "turns", "sessions", "users",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
