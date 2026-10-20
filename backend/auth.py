"""JWT auth, password hashing, RBAC + branch scoping."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response

from db import db
from models import UserPublic, Role

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO = "HS256"
ACCESS_TTL_MIN = 15
REFRESH_TTL_DAYS = 7


def validate_password(plain: str):
    if len(plain) < 8 or not any(c.isalpha() for c in plain) or not any(c.isdigit() for c in plain):
        raise HTTPException(400, "Password must be at least 8 characters with letters and numbers")


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


def make_access_token(user: UserPublic, tv: int = 0) -> str:
    return _make_token(
        {"sub": user.id, "role": user.role, "branch_id": user.branch_id, "typ": "access", "tv": tv},
        timedelta(minutes=ACCESS_TTL_MIN),
    )


def make_refresh_token(user: UserPublic, tv: int = 0) -> str:
    return _make_token(
        {"sub": user.id, "typ": "refresh", "tv": tv},
        timedelta(days=REFRESH_TTL_DAYS),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


ACCESS_COOKIE = "swarna_access"
REFRESH_COOKIE = "swarna_refresh"


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie(ACCESS_COOKIE, access, httponly=True, secure=True, samesite="lax",
                        max_age=ACCESS_TTL_MIN * 60, path="/api")
    response.set_cookie(REFRESH_COOKIE, refresh, httponly=True, secure=True, samesite="lax",
                        max_age=REFRESH_TTL_DAYS * 86400, path="/api/auth")


def clear_auth_cookies(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/api", secure=True, httponly=True, samesite="lax")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth", secure=True, httponly=True, samesite="lax")


async def get_current_user(request: Request) -> UserPublic:
    token = request.cookies.get(ACCESS_COOKIE)
    authorization = request.headers.get("Authorization", "")
    if not token and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="Not an access token")
    doc = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not doc or not doc.get("active", True):
        raise HTTPException(status_code=401, detail="User not found or inactive")
    if payload.get("tv", 0) != doc.get("token_version", 0):
        raise HTTPException(status_code=401, detail="Session revoked, please sign in again")
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
