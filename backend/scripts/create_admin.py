# ─────────────────────────────────────────────────────────────────────────────
# scripts/create_admin.py
# One-shot script to create the first admin user.
# Run ONCE after `make migrate`:
#   python scripts/create_admin.py --email admin@hopital.tg --password "..."
# ─────────────────────────────────────────────────────────────────────────────
"""
#!/usr/bin/env python3
import argparse
import asyncio
import os
import asyncpg
import bcrypt

async def main(email: str, password: str, roles: list[str]) -> None:
    pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"], min_size=1, max_size=2
    )
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    row = await pool.fetchrow(
        \"\"\"
        INSERT INTO users (email, hashed_pw, roles)
        VALUES ($1, $2, $3)
        ON CONFLICT (email) DO UPDATE
            SET hashed_pw = EXCLUDED.hashed_pw,
                roles     = EXCLUDED.roles,
                active    = true
        RETURNING id, email, roles
        \"\"\",
        email, hashed, roles,
    )
    print(f"✓ User created: {row['email']} roles={row['roles']} id={row['id']}")
    await pool.close()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--email",    required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--roles",    default="admin,clinician")
    args = p.parse_args()
    asyncio.run(main(args.email, args.password, args.roles.split(",")))
"""
