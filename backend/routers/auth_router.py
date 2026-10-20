"""Auth endpoints: login, refresh, me, user CRUD (admin)."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
from pydantic import BaseModel

from db import db
from models import (
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserPublic,
    Role,
    now_iso,
    new_id,
)
from auth import (
    validate_password,
    verify_password,
    hash_password,
    make_access_token,
    make_refresh_token,
    decode_token,
    get_current_user,
    require_roles,
)
from audit import log_event

router = APIRouter(prefix="/auth", tags=["auth"])


MAX_ATTEMPTS = 5
LOCK_MINUTES = 15


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _tokens(doc: dict) -> TokenPair:
    user = UserPublic(**{k: v for k, v in doc.items() if k != "password_hash"})
    tv = doc.get("token_version", 0)
    return TokenPair(access_token=make_access_token(user, tv),
                     refresh_token=make_refresh_token(user, tv), user=user)


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, request: Request):
    email = body.email.lower()
    ident = f"{_client_ip(request)}:{email}"
    now = datetime.now(timezone.utc)
    att = await db.login_attempts.find_one({"identifier": ident}, {"_id": 0})
    locked = att and att.get("locked_until")
    if locked and datetime.fromisoformat(locked) > now:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    doc = await db.users.find_one({"email": email}, {"_id": 0})
    if not doc or not verify_password(body.password, doc["password_hash"]):
        count = 1 if locked else (att or {}).get("count", 0) + 1
        until = (now + timedelta(minutes=LOCK_MINUTES)).isoformat() if count >= MAX_ATTEMPTS else None
        await db.login_attempts.update_one(
            {"identifier": ident}, {"$set": {"count": count, "locked_until": until}}, upsert=True)
        await log_event("auth", "login_failed", diff={"email": email})
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not doc.get("active", True):
        raise HTTPException(status_code=403, detail="Account deactivated. Contact your admin.")
    await db.login_attempts.delete_one({"identifier": ident})
    await log_event("auth", "login", user_id=doc["id"], branch_id=doc.get("branch_id"))
    return _tokens(doc)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest):
    payload = decode_token(body.refresh_token)
    if payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    doc = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not doc or not doc.get("active", True):
        raise HTTPException(status_code=401, detail="User not found")
    if payload.get("tv", 0) != doc.get("token_version", 0):
        raise HTTPException(status_code=401, detail="Session revoked, please sign in again")
    return _tokens(doc)


@router.get("/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(get_current_user)):
    return user


@router.get("/users", response_model=List[UserPublic])
async def list_users(user: UserPublic = Depends(require_roles("admin", "manager"))):
    q = {} if user.role == "admin" else {"branch_id": user.branch_id}
    docs = await db.users.find(q, {"_id": 0, "password_hash": 0}).to_list(500)
    return [UserPublic(**d) for d in docs]


@router.post("/users", response_model=UserPublic)
async def create_user(
    body: UserCreate, actor: UserPublic = Depends(require_roles("admin"))
):
    validate_password(body.password)
    await _check_branch(body.role, body.branch_id)
    existing = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user_doc = {
        "id": new_id(),
        "email": body.email.lower(),
        "name": body.name,
        "role": body.role,
        "branch_id": body.branch_id,
        "active": True,
        "created_at": now_iso(),
        "password_hash": hash_password(body.password),
    }
    await db.users.insert_one(user_doc)
    await log_event(
        "user", "create", entity_id=user_doc["id"], user_id=actor.id,
        diff={"email": user_doc["email"], "role": user_doc["role"]},
    )
    user_doc.pop("password_hash")
    return UserPublic(**user_doc)


async def _check_branch(role: str, branch_id: Optional[str]):
    if role != "admin" and not branch_id:
        raise HTTPException(400, "Branch is required for non-admin staff")
    if branch_id and not await db.branches.find_one({"id": branch_id}, {"_id": 0, "id": 1}):
        raise HTTPException(400, "Branch not found")


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[Role] = None
    branch_id: Optional[str] = None
    active: Optional[bool] = None


class PasswordReset(BaseModel):
    password: str


async def _get_user(user_id: str) -> dict:
    doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "User not found")
    return doc


@router.patch("/users/{user_id}", response_model=UserPublic)
async def update_user(user_id: str, body: UserUpdate,
                      actor: UserPublic = Depends(require_roles("admin"))):
    doc = await _get_user(user_id)
    changes = body.model_dump(exclude_unset=True)
    if user_id == actor.id and (changes.get("role", "admin") != "admin"
                                or changes.get("active") is False):
        raise HTTPException(400, "You cannot demote or deactivate your own account")
    await _check_branch(changes.get("role", doc["role"]),
                        changes.get("branch_id", doc.get("branch_id")))
    update = {"$set": changes}
    if any(k in changes for k in ("role", "branch_id", "active")):
        update["$inc"] = {"token_version": 1}
    await db.users.update_one({"id": user_id}, update)
    await log_event("user", "update", entity_id=user_id, user_id=actor.id, diff=changes)
    return UserPublic(**{k: v for k, v in (await _get_user(user_id)).items()
                         if k != "password_hash"})


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, body: PasswordReset,
                         actor: UserPublic = Depends(require_roles("admin"))):
    await _get_user(user_id)
    validate_password(body.password)
    await db.users.update_one({"id": user_id}, {
        "$set": {"password_hash": hash_password(body.password)},
        "$inc": {"token_version": 1}})
    await log_event("user", "reset_password", entity_id=user_id, user_id=actor.id)
    return {"ok": True}
