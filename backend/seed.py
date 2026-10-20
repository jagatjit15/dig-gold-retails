"""Seed initial admin user, branches, purities, categories, daily rates.
Runs idempotently on server startup."""
from db import db
from auth import hash_password
from models import (
    Branch, Purity, Category, DailyRate, now_iso, new_id,
)


SEED_ADMIN_EMAIL = "admin@swarnaerp.in"
SEED_ADMIN_PASSWORD = "Admin@12345"


async def seed_if_empty():
    # Admin user
    if not await db.users.find_one({"email": SEED_ADMIN_EMAIL}):
        await db.users.insert_one({
            "id": new_id(),
            "email": SEED_ADMIN_EMAIL,
            "name": "System Admin",
            "role": "admin",
            "branch_id": None,
            "active": True,
            "created_at": now_iso(),
            "password_hash": hash_password(SEED_ADMIN_PASSWORD),
        })

    # Branches
    if await db.branches.count_documents({}) == 0:
        branches = [
            Branch(code="ZB-MAIN", name="Zaveri Bazar Main",
                   address="Zaveri Bazar, Mumbai, MH",
                   gstin="27AAAAA0000A1Z5", state_code="27"),
            Branch(code="MG-BLR", name="MG Road Store",
                   address="MG Road, Bengaluru, KA",
                   gstin="29BBBBB1111B2Z4", state_code="29"),
        ]
        await db.branches.insert_many([b.model_dump() for b in branches])

    # Purities
    if await db.purities.count_documents({}) == 0:
        purities = [
            Purity(code="24K", label="24K Gold (99.9%)",
                   metal="gold", fineness=0.999),
            Purity(code="22K916", label="22K Gold (91.6%)",
                   metal="gold", fineness=0.916),
            Purity(code="18K", label="18K Gold (75.0%)",
                   metal="gold", fineness=0.750),
            Purity(code="925", label="925 Sterling Silver",
                   metal="silver", fineness=0.925),
            Purity(code="PT950", label="950 Platinum",
                   metal="platinum", fineness=0.950),
        ]
        await db.purities.insert_many([p.model_dump() for p in purities])

    # Categories
    if await db.categories.count_documents({}) == 0:
        cats = [
            Category(name="Rings", hsn_code="7113", gst_rate=3.0),
            Category(name="Necklaces", hsn_code="7113", gst_rate=3.0),
            Category(name="Bangles", hsn_code="7113", gst_rate=3.0),
            Category(name="Earrings", hsn_code="7113", gst_rate=3.0),
            Category(name="Coins", hsn_code="7118", gst_rate=3.0),
            Category(name="Silver Articles", hsn_code="7114", gst_rate=3.0),
        ]
        await db.categories.insert_many([c.model_dump() for c in cats])

    # Daily rates for today
    today = now_iso()[:10]
    if await db.daily_rates.count_documents({"rate_date": today}) == 0:
        rates = [
            DailyRate(rate_date=today, metal="gold", purity_code="24K",
                      rate_per_gram=7450.0),
            DailyRate(rate_date=today, metal="gold", purity_code="22K916",
                      rate_per_gram=6830.0),
            DailyRate(rate_date=today, metal="gold", purity_code="18K",
                      rate_per_gram=5590.0),
            DailyRate(rate_date=today, metal="silver", purity_code="925",
                      rate_per_gram=88.50),
            DailyRate(rate_date=today, metal="platinum", purity_code="PT950",
                      rate_per_gram=3200.0),
        ]
        await db.daily_rates.insert_many([r.model_dump() for r in rates])
