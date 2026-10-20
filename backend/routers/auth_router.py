"""Auth endpoints: login, refresh, me, user CRUD (admin)."""
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from db import db
from models import (
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserPublic,
    now_iso,
    new_id,
)
from auth import (
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


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest):
    doc = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not doc or not verify_password(body.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not doc.get("active", True):
        raise HTTPException(status_code=403, detail="User inactive")
    user = UserPublic(**{k: v for k, v in doc.items() if k != "password_hash"})
    access = make_access_token(user)
    refresh = make_refresh_token(user)
    await log_event("auth", "login", user_id=user.id, branch_id=user.branch_id)
    return TokenPair(access_token=access, refresh_token=refresh, user=user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest):
    payload = decode_token(body.refresh_token)
    if payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    doc = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not doc or not doc.get("active", True):
        raise HTTPException(status_code=401, detail="User not found")
    user = UserPublic(**{k: v for k, v in doc.items() if k != "password_hash"})
    return TokenPair(
        access_token=make_access_token(user),
        refresh_token=make_refresh_token(user),
        user=user,
    )


@router.get("/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(get_current_user)):
    return user


@router.get("/users", response_model=List[UserPublic])
async def list_users(_: UserPublic = Depends(require_roles("admin", "manager"))):
    docs = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return [UserPublic(**d) for d in docs]


@router.post("/users", response_model=UserPublic)
async def create_user(
    body: UserCreate, actor: UserPublic = Depends(require_roles("admin"))
):
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
