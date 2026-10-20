"""JWT auth, password hashing, RBAC + branch scoping."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Header, status
from pydantic import BaseModel

from db import db
from models import UserInDB, UserPublic, Role

# Secret: pick up from env, fallback dev-only secret (fail-fast philosophy means
# in prod this must be set).
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-secret-change-me")
JWT_ALGO = "HS256"
ACCESS_TTL_MIN = 60
REFRESH_TTL_DAYS = 7


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _make_token(payload: dict, expires_delta: timedelta) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + expires_delta
    data["iat"] = datetime.now(timezone.utc)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGO)


def make_access_token(user: UserPublic) -> str:
    return _make_token(
        {"sub": user.id, "role": user.role, "branch_id": user.branch_id, "typ": "access"},
        timedelta(minutes=ACCESS_TTL_MIN),
    )


def make_refresh_token(user: UserPublic) -> str:
    return _make_token(
        {"sub": user.id, "typ": "refresh"},
        timedelta(days=REFRESH_TTL_DAYS),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserPublic:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="Not an access token")
    doc = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not doc or not doc.get("active", True):
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return UserPublic(**{k: v for k, v in doc.items() if k != "password_hash"})


def require_roles(*roles: Role):
    async def _dep(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role in {list(roles)}",
            )
        return user
    return _dep


def branch_scope_ok(user: UserPublic, branch_id: str) -> bool:
    """Admins see all branches; others only their own."""
    if user.role == "admin":
        return True
    return user.branch_id == branch_id


def enforce_branch(user: UserPublic, branch_id: str):
    if not branch_scope_ok(user, branch_id):
        raise HTTPException(
            status_code=403,
            detail="Branch scope violation",
        )
