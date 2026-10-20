"""Branches, Purities, Categories, Daily Rates."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from db import db
from models import (
    Branch, BranchCreate,
    Purity, PurityCreate,
    Category, CategoryCreate,
    DailyRate, DailyRateCreate,
    UserPublic, now_iso,
)
from auth import get_current_user, require_roles
from audit import log_event

router = APIRouter(tags=["masters"])


# ---- Branches ----
@router.get("/branches", response_model=List[Branch])
async def list_branches(_: UserPublic = Depends(get_current_user)):
    docs = await db.branches.find({}, {"_id": 0}).to_list(500)
    return [Branch(**d) for d in docs]


@router.post("/branches", response_model=Branch)
async def create_branch(
    body: BranchCreate, user: UserPublic = Depends(require_roles("admin"))
):
    exists = await db.branches.find_one({"code": body.code}, {"_id": 0})
    if exists:
        raise HTTPException(409, "Branch code already exists")
    br = Branch(**body.model_dump())
    await db.branches.insert_one(br.model_dump())
    await log_event("branch", "create", entity_id=br.id, user_id=user.id,
                    diff=br.model_dump())
    return br


# ---- Purities ----
@router.get("/purities", response_model=List[Purity])
async def list_purities(_: UserPublic = Depends(get_current_user)):
    docs = await db.purities.find({}, {"_id": 0}).to_list(200)
    return [Purity(**d) for d in docs]


@router.post("/purities", response_model=Purity)
async def create_purity(
    body: PurityCreate, user: UserPublic = Depends(require_roles("admin", "manager"))
):
    exists = await db.purities.find_one({"code": body.code}, {"_id": 0})
    if exists:
        raise HTTPException(409, "Purity code already exists")
    p = Purity(**body.model_dump())
    await db.purities.insert_one(p.model_dump())
    await log_event("purity", "create", entity_id=p.id, user_id=user.id,
                    diff=p.model_dump())
    return p


# ---- Categories ----
@router.get("/categories", response_model=List[Category])
async def list_categories(_: UserPublic = Depends(get_current_user)):
    docs = await db.categories.find({}, {"_id": 0}).to_list(500)
    return [Category(**d) for d in docs]


@router.post("/categories", response_model=Category)
async def create_category(
    body: CategoryCreate, user: UserPublic = Depends(require_roles("admin", "manager"))
):
    c = Category(**body.model_dump())
    await db.categories.insert_one(c.model_dump())
    await log_event("category", "create", entity_id=c.id, user_id=user.id,
                    diff=c.model_dump())
    return c


# ---- Daily Rates ----
@router.get("/daily-rates", response_model=List[DailyRate])
async def list_daily_rates(
    rate_date: Optional[str] = Query(None),
    _: UserPublic = Depends(get_current_user),
):
    q = {}
    if rate_date:
        q["rate_date"] = rate_date
    docs = await db.daily_rates.find(q, {"_id": 0}).sort(
        [("rate_date", -1)]
    ).to_list(500)
    return [DailyRate(**d) for d in docs]


@router.get("/daily-rates/latest", response_model=List[DailyRate])
async def latest_daily_rates(_: UserPublic = Depends(get_current_user)):
    """Return latest rate per (metal, purity_code)."""
    pipeline = [
        {"$sort": {"rate_date": -1, "created_at": -1}},
        {"$group": {
            "_id": {"metal": "$metal", "purity_code": "$purity_code"},
            "doc": {"$first": "$$ROOT"},
        }},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0}},
    ]
    docs = await db.daily_rates.aggregate(pipeline).to_list(100)
    return [DailyRate(**d) for d in docs]


@router.post("/daily-rates", response_model=DailyRate)
async def set_daily_rate(
    body: DailyRateCreate,
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    r = DailyRate(**body.model_dump(), set_by=user.id)
    await db.daily_rates.insert_one(r.model_dump())
    await log_event("daily_rate", "create", entity_id=r.id, user_id=user.id,
                    diff=r.model_dump())
    return r
