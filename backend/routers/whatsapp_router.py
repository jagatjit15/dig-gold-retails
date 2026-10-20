"""WhatsApp: invoice send, broadcasts, outbox."""
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import db
from models import UserPublic, new_id
from auth import get_current_user, require_roles, enforce_branch
from audit import log_event
from whatsapp import get_provider, normalize_phone, record_message, send_invoice_message

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.get("/status")
async def status(_: UserPublic = Depends(get_current_user)):
    p = get_provider()
    return {"provider": p.name, "mocked": p.mocked}


@router.post("/invoices/{bill_id}")
async def send_invoice(bill_id: str,
                       user: UserPublic = Depends(require_roles("admin", "manager", "billing"))):
    bill = await db.bills.find_one({"id": bill_id}, {"_id": 0})
    if not bill:
        raise HTTPException(404, "Bill not found")
    enforce_branch(user, bill["branch_id"])
    if not bill.get("customer_phone"):
        raise HTTPException(400, "Bill has no customer phone number")
    branch = await db.branches.find_one({"id": bill["branch_id"]}, {"_id": 0})
    rec = await send_invoice_message(bill, branch, user.id)
    await db.bills.update_one({"id": bill_id}, {"$set": {"whatsapp_status": rec["status"]}})
    return rec


class Broadcast(BaseModel):
    branch_id: str
    message: str = Field(min_length=1, max_length=1000)
    audience: Literal["customers", "custom"] = "customers"
    phones: List[str] = []


BROADCASTS_PER_HOUR = 10


async def check_broadcast_quota(branch_id: str) -> str:
    """Reserve a campaign slot first, then count, so concurrent requests can't exceed the limit."""
    now = datetime.now(timezone.utc)
    campaign = new_id()
    await db.broadcast_campaigns.insert_one({"id": campaign, "branch_id": branch_id,
                                             "created_at": now.isoformat()})
    since = (now - timedelta(hours=1)).isoformat()
    total = await db.broadcast_campaigns.count_documents(
        {"branch_id": branch_id, "created_at": {"$gte": since}})
    if total > BROADCASTS_PER_HOUR:
        await db.broadcast_campaigns.delete_one({"id": campaign})
        raise HTTPException(429, f"Limit of {BROADCASTS_PER_HOUR} broadcasts per hour reached for this branch")
    return campaign


async def resolve_recipients(branch_id: str, audience: str, phones: List[str]):
    raw = phones if audience == "custom" else await db.bills.distinct(
        "customer_phone", {"branch_id": branch_id, "customer_phone": {"$nin": [None, ""]}})
    numbers = {normalize_phone(p) for p in raw}
    invalid = sum(1 for p in raw if not normalize_phone(p))
    numbers.discard(None)
    if not numbers:
        raise HTTPException(400, "No valid recipient numbers")
    if len(numbers) > 1000:
        raise HTTPException(400, "Maximum 1000 recipients per broadcast")
    return sorted(numbers), invalid, await check_broadcast_quota(branch_id)


@router.post("/broadcast")
async def broadcast(body: Broadcast,
                    user: UserPublic = Depends(require_roles("admin", "manager"))):
    enforce_branch(user, body.branch_id)
    numbers, invalid, campaign = await resolve_recipients(body.branch_id, body.audience, body.phones)
    provider = get_provider()
    counts = {"sent": 0, "failed": 0}
    for to in numbers:
        try:
            res = await provider.send_text(to, body.message)
            st, err = res.get("status", "sent"), None
            counts["sent"] += 1
        except Exception as e:
            st, err = "failed", str(e)
            counts["failed"] += 1
        await record_message(kind="broadcast", campaign_id=campaign, branch_id=body.branch_id,
                             to=to, text=body.message, status=st, error=err,
                             provider=provider.name, created_by=user.id)
    await log_event("whatsapp", "broadcast", entity_id=campaign, user_id=user.id,
                    branch_id=body.branch_id, diff={"recipients": len(numbers), **counts})
    return {"campaign_id": campaign, "recipients": len(numbers), "invalid_skipped": invalid,
            "mocked": provider.mocked, **counts}


@router.get("/messages")
async def messages(branch_id: str, kind: Optional[str] = None,
                   user: UserPublic = Depends(get_current_user)):
    enforce_branch(user, branch_id)
    q = {"branch_id": branch_id, **({"kind": kind} if kind else {})}
    return await db.whatsapp_messages.find(q, {"_id": 0}).sort(
        [("created_at", -1)]).to_list(200)
