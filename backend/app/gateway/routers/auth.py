#  ─────────────────────────────────────────────────────────────────────────────
# tropicare_gateway/routers/auth.py
# ─────────────────────────────────────────────────────────────────────────────

import math
import os
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import asyncpg
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

# ── Account lockout constants ─────────────────────────────────────────────────

_FAIL_KEY = "auth:fail:{email}"    # tracks failure count, 30min TTL
_LOCK_KEY = "auth:lock:{email}"    # lockout flag, 15min TTL

MAX_FAILED_ATTEMPTS = 5
FAIL_WINDOW_SECONDS = 1800   # 30 minutes
LOCK_DURATION_SECONDS = 900  # 15 minutes

# ── Key loading ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _private_key() -> str:
    path = os.getenv("JWT_PRIVATE_KEY_PATH", "keys/private.pem")
    return open(path).read()

@lru_cache(maxsize=1)
def _public_key() -> str:
    path = os.getenv("JWT_PUBLIC_KEY_PATH", "keys/public.pem")
    return open(path).read()

TOKEN_TTL_HOURS   = 8
REFRESH_TTL_DAYS  = 30
ALGORITHM         = "RS256"

# ── Token helpers ─────────────────────────────────────────────────────────────

def _sign(payload: dict, expires_delta: timedelta) -> str:
    exp = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        {**payload, "exp": exp, "iat": datetime.now(timezone.utc)},
        _private_key(),
        algorithm=ALGORITHM,
    )

def _make_tokens(user: dict) -> dict:
    base = {
        "sub":   str(user["id"]),
        "email": user["email"],
        "roles": user["roles"],
    }
    return {
        "access_token":  _sign({**base, "type": "access"},  timedelta(hours=TOKEN_TTL_HOURS)),
        "refresh_token": _sign({**base, "type": "refresh"}, timedelta(days=REFRESH_TTL_DAYS)),
        "token_type":    "bearer",
    }

def _verify(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, _public_key(), algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise ValueError("wrong token type")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Token invalide : {exc}")

# ── Request / Response models ─────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str = Field(max_length=5000)

class LoginResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str = Field(max_length=5000)

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=5000)
    new_password:     str = Field(max_length=5000)

class CreateUserRequest(BaseModel):
    email:    EmailStr
    password: str = Field(max_length=5000)
    roles:    list[str] = ["clinician"]

class RegisterRequest(BaseModel):
    email:    EmailStr
    password: str = Field(max_length=5000)
    role:     str = Field(default="clinician", max_length=5000)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pg_pool

async def _fetch_user(pool: asyncpg.Pool, email: str) -> dict | None:
    row = await pool.fetchrow(
        "SELECT id, email, hashed_pw, roles, active FROM users WHERE email = $1",
        email,
    )
    return dict(row) if row else None

async def _fetch_user_by_id(pool: asyncpg.Pool, user_id: str) -> dict | None:
    row = await pool.fetchrow(
        "SELECT id, email, roles, active FROM users WHERE id = $1",
        user_id,
    )
    return dict(row) if row else None

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def _check(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def _safe_user(u: dict) -> dict:
    return {"id": str(u["id"]), "email": u["email"], "roles": u["roles"]}

# ── Redis + lockout helpers ───────────────────────────────────────────────────

def _redis(request: Request):
    """Get the Redis client from the session store."""
    return request.app.state.session_store._redis


async def _check_lockout(request: Request, email: str) -> None:
    """Raise HTTP 423 if the account is currently locked."""
    r = _redis(request)
    lock_key = _LOCK_KEY.format(email=email)
    ttl = await r.ttl(lock_key)
    if ttl > 0:
        minutes_left = math.ceil(ttl / 60)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked — retry in {minutes_left} minutes",
        )


async def _record_failed_attempt(request: Request, email: str) -> None:
    """Increment failure counter; lock account when threshold is reached."""
    r = _redis(request)
    fail_key = _FAIL_KEY.format(email=email)

    count = await r.incr(fail_key)
    if count == 1:
        # First failure — set the 30-minute sliding window
        await r.expire(fail_key, FAIL_WINDOW_SECONDS)

    if count >= MAX_FAILED_ATTEMPTS:
        lock_key = _LOCK_KEY.format(email=email)
        await r.set(lock_key, "1", ex=LOCK_DURATION_SECONDS)
        # Reset the failure counter so it doesn't keep growing
        await r.delete(fail_key)


async def _clear_failed_attempts(request: Request, email: str) -> None:
    """Clear failure counter on successful login."""
    r = _redis(request)
    fail_key = _FAIL_KEY.format(email=email)
    await r.delete(fail_key)

def _validate_password(password: str) -> None:
    """Validate password strength. Raises HTTPException(422) on failure."""
    if len(password) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be ≥10 chars with upper, lower, digit",
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be ≥10 chars with upper, lower, digit",
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be ≥10 chars with upper, lower, digit",
        )
    if not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be ≥10 chars with upper, lower, digit",
        )

# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
@limiter.limit("10/minute")
async def register(body: RegisterRequest, request: Request):
    """Public endpoint: register a new user account."""
    _validate_password(body.password)
    pool = _pool(request)
    existing = await _fetch_user(pool, body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    hashed = _hash(body.password)
    row = await pool.fetchrow(
        "INSERT INTO users (email, hashed_pw, roles) VALUES ($1,$2,$3) RETURNING id, email",
        body.email, hashed, [body.role],
    )
    return {"user_id": str(row["id"]), "email": row["email"]}


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(body: LoginRequest, request: Request):
    pool = _pool(request)

    # 1. Check if account is locked
    await _check_lockout(request, body.email)

    user = await _fetch_user(pool, body.email)

    if not user or not user["active"]:
        # Constant-time path even when user not found
        bcrypt.checkpw(b"dummy", bcrypt.hashpw(b"dummy", bcrypt.gensalt()))
        await _record_failed_attempt(request, body.email)
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    if not _check(body.password, user["hashed_pw"]):
        await _record_failed_attempt(request, body.email)
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    # 3. Successful login — clear failure counter
    await _clear_failed_attempts(request, body.email)

    tokens = _make_tokens(user)
    return LoginResponse(**tokens, user=_safe_user(user))


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh(body: RefreshRequest, request: Request):
    payload = _verify(body.refresh_token, expected_type="refresh")
    pool    = _pool(request)
    user    = await _fetch_user_by_id(pool, payload["sub"])

    if not user or not user["active"]:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou désactivé")

    tokens = _make_tokens(user)
    return tokens


@router.get("/me")
async def me(request: Request):
    user = _verify(_bearer_token(request))
    pool = _pool(request)
    row  = await _fetch_user_by_id(pool, user["sub"])
    if not row:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return _safe_user(row)


@router.post("/change-password", status_code=204)
async def change_password(
    body:    ChangePasswordRequest,
    request: Request,
):
    user = _verify(_bearer_token(request))
    pool = _pool(request)
    row  = await pool.fetchrow(
        "SELECT id, hashed_pw FROM users WHERE id = $1", user["sub"]
    )
    if not row or not _check(body.current_password, row["hashed_pw"]):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    _validate_password(body.new_password)
    await pool.execute(
        "UPDATE users SET hashed_pw = $1 WHERE id = $2", _hash(body.new_password), row["id"]
    )


@router.post("/users", status_code=201)
async def create_user(body: CreateUserRequest, request: Request):
    """Admin-only: create a new user account."""
    _require_admin(_verify(_bearer_token(request)))
    _validate_password(body.password)
    pool     = _pool(request)
    existing = await _fetch_user(pool, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email déjà utilisé")
    hashed = _hash(body.password)
    row = await pool.fetchrow(
        "INSERT INTO users (email, hashed_pw, roles) VALUES ($1,$2,$3) RETURNING id,email,roles",
        body.email, hashed, body.roles,
    )
    return _safe_user(dict(row))


@router.get("/users")
async def list_users(request: Request):
    """Admin-only: list all users."""
    _require_admin(_verify(_bearer_token(request)))
    pool = _pool(request)
    rows = await pool.fetch(
        "SELECT id, email, roles, active, created_at FROM users ORDER BY created_at DESC"
    )
    return [
        {"id": str(r["id"]), "email": r["email"], "roles": r["roles"],
         "active": r["active"], "created_at": r["created_at"].isoformat()}
        for r in rows
    ]


@router.patch("/users/{user_id}/deactivate", status_code=204)
async def deactivate_user(user_id: str, request: Request):
    _require_admin(_verify(_bearer_token(request)))
    await _pool(request).execute(
        "UPDATE users SET active = false WHERE id = $1", user_id
    )


# ── Internal helpers replacing the broken __wrapped__ pattern ─────────────────

def _bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Non authentifié")
    return auth[7:]


def _require_admin(payload: dict) -> None:
    if "admin" not in (payload.get("roles") or []):
        raise HTTPException(status_code=403, detail="Rôle admin requis")


async def _current_user_from_request(request: Request) -> dict:  # kept for compatibility
    return _verify(_bearer_token(request))

