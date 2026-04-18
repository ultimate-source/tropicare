#!/usr/bin/env python3
"""Create the default admin user. Run inside the gateway container."""
import asyncio
import os
import asyncpg
import bcrypt

async def main():
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    pw = b"AdminPass123"
    hashed = bcrypt.hashpw(pw, bcrypt.gensalt(12)).decode()
    row = await pool.fetchrow(
        "INSERT INTO users (email, hashed_pw, roles) "
        "VALUES ($1, $2, $3) "
        "ON CONFLICT (email) DO UPDATE "
        "SET hashed_pw = EXCLUDED.hashed_pw, roles = EXCLUDED.roles "
        "RETURNING id, email, roles",
        "admin@tropicare.health", hashed, ["admin", "clinician"],
    )
    print(f"Created: {row['email']} roles={row['roles']} id={row['id']}")
    await pool.close()

asyncio.run(main())
