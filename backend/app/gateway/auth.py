# ─────────────────────────────────────────────────────────────────────────────
# tropicare_gateway/auth.py  — JWT RS256 middleware
# ─────────────────────────────────────────────────────────────────────────────
import os

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from functools import lru_cache

_bearer = HTTPBearer()


@lru_cache(maxsize=1)
def _public_key() -> str:
    path = os.getenv("JWT_PUBLIC_KEY_PATH", "keys/public.pem")
    return open(path).read()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            _public_key(),
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalide : {e}",
        )


def require_role(role: str):
    async def check(user: dict = Depends(get_current_user)):
        if role not in user.get("roles", []):
            raise HTTPException(status_code=403, detail="Rôle insuffisant")
        return user
    return check
