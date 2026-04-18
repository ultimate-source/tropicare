# ─────────────────────────────────────────────────────────────────────────────
# alembic/versions/0007_seed_dev_users.py
# Seeds default admin and clinician users for local development.
# ─────────────────────────────────────────────────────────────────────────────
"""Seed dev users (admin + clinician)

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import bcrypt

revision      = "0007"
down_revision = "0006"

ADMIN_EMAIL    = "admin@tropicare.health"
ADMIN_PASSWORD = "AdminPass123"
ADMIN_ROLES    = "{admin,clinician}"

CLINIC_EMAIL    = "clinician@tropicare.health"
CLINIC_PASSWORD = "ClinicPass123"
CLINIC_ROLES    = "{clinician}"


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(12)).decode()


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO users (email, hashed_pw, roles, active)
        VALUES ('{ADMIN_EMAIL}', '{_hash(ADMIN_PASSWORD)}', '{ADMIN_ROLES}', true)
        ON CONFLICT (email) DO UPDATE
            SET hashed_pw = EXCLUDED.hashed_pw,
                roles     = EXCLUDED.roles,
                active    = true
        """
    )
    op.execute(
        f"""
        INSERT INTO users (email, hashed_pw, roles, active)
        VALUES ('{CLINIC_EMAIL}', '{_hash(CLINIC_PASSWORD)}', '{CLINIC_ROLES}', true)
        ON CONFLICT (email) DO UPDATE
            SET hashed_pw = EXCLUDED.hashed_pw,
                roles     = EXCLUDED.roles,
                active    = true
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM users WHERE email IN ('{ADMIN_EMAIL}', '{CLINIC_EMAIL}')")
