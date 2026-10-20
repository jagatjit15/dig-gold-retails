"""Launch lookbook cards: build from item photos, store, broadcast on WhatsApp."""
import asyncio
import uuid
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import db
from models import UserPublic, new_id, now_iso
from auth import get_current_user, require_roles, enforce_branch
from audit import log_event
from lookbook import build_card, inr
from storage import APP_NAME, get_object, put_object
from whatsapp import get_provider, record_message
from routers.billing_router import _price_lines
from routers.whatsapp_router import resolve_recipients

router = APIRouter(prefix="/lookbook", tags=["lookbook"])
managers = require_roles("admin", "manager")


class CardCreate(BaseModel):
    branch_id: str
    title: str = Field(min_length=1, max_length=60)
    subtitle: Optional[str] = Field(default=None, max_length=80)
    item_ids: List[str] = Field(min_length=1, max_length=6)


class CardBroadcast(BaseModel):
    message: str = Field(default="", max_length=1000)
    audience: Literal["customers", "custom"] = "customers"
    phones: List[str] = []


async def _photo(item_id: str) -> Optional[bytes]:
    f = await db.files.find_one({"owner_type": "item", "owner_id": item_id, "is_deleted": False,
                                 "content_type": {"$regex": "^image/"}}, {"_id": 0},
                                sort=[("created_at", 1)])
    if not f:
        return None
    try:
        return (await asyncio.to_thread(get_object, f["storage_path"]))[0]
    except Exception:
        return None


@router.post("")
async def create_card(body: CardCreate, user: UserPublic = Depends(managers)):
    enforce_branch(user, body.branch_id)
    branch = await db.branches.find_one({"id": body.branch_id}, {"_id": 0})
    ids = list(dict.fromkeys(body.item_ids))
    items = await db.items.find({"id": {"$in": ids}, "branch_id": body.branch_id}, {"_id": 0}).to_list(6)
    if len(items) != len(ids):
        raise HTTPException(400, "Items must exist in this branch")
    items.sort(key=lambda i: ids.index(i["id"]))
    lines = await _price_lines(items, {})
    cats = {c["id"]: c["name"] for c in await db.categories.find({}, {"_id": 0}).to_list(500)}
    tiles = []
    for it, ln in zip(items, lines):
        price = round(ln.taxable * (1 + ln.gst_rate / 100))
        tiles.append({"photo": await _photo(it["id"]),
                      "name": it.get("description") or f"{cats.get(it['category_id'], 'Jewellery')} · {it['tag_id']}",
                      "detail": f"{ln.purity_code} · {it['net_wt']:.3f} g net",
                      "price": inr(price)})
    footer = f"{branch['name']} · {branch.get('address') or ''} · Prices incl. GST at today's rate, subject to change"
    png = await asyncio.to_thread(build_card, body.title, body.subtitle, branch["name"], footer, tiles)
    path = f"{APP_NAME}/lookbook/{body.branch_id}/{uuid.uuid4()}.png"
    result = await asyncio.to_thread(put_object, path, png, "image/png")
    file_id = new_id()
    await db.files.insert_one({
        "id": file_id, "owner_type": "branch", "owner_id": body.branch_id,
        "branch_id": body.branch_id, "category": "lookbook",
        "original_filename": f"{body.title[:40]}.png", "content_type": "image/png",
        "size": result.get("size", len(png)), "uploaded_by": user.id, "created_at": now_iso(),
        "storage_path": result["path"], "is_deleted": False})
    card = {"id": new_id(), "branch_id": body.branch_id, "title": body.title,
            "subtitle": body.subtitle, "item_ids": ids, "file_id": file_id,
            "created_by": user.id, "created_at": now_iso()}
    await db.lookbooks.insert_one(dict(card))
    await log_event("lookbook", "create", entity_id=card["id"], user_id=user.id,
                    branch_id=body.branch_id, diff={"title": body.title, "items": len(ids)})
    return card


@router.get("")
async def list_cards(branch_id: str, user: UserPublic = Depends(get_current_user)):
    enforce_branch(user, branch_id)
    return await db.lookbooks.find({"branch_id": branch_id}, {"_id": 0}).sort(
        [("created_at", -1)]).to_list(100)


@router.post("/{card_id}/broadcast")
async def broadcast_card(card_id: str, body: CardBroadcast, user: UserPublic = Depends(managers)):
    card = await db.lookbooks.find_one({"id": card_id}, {"_id": 0})
    if not card:
        raise HTTPException(404, "Lookbook card not found")
    enforce_branch(user, card["branch_id"])
    numbers, invalid = await resolve_recipients(card["branch_id"], body.audience, body.phones)
    f = await db.files.find_one({"id": card["file_id"]}, {"_id": 0})
    png = (await asyncio.to_thread(get_object, f["storage_path"]))[0]
    caption = body.message or card["title"]
    provider = get_provider()
    campaign, counts = new_id(), {"sent": 0, "failed": 0}
    for to in numbers:
        try:
            res = await provider.send_image(to, f"{card['title']}.png", png, caption)
            st, err = res.get("status", "sent"), None
            counts["sent"] += 1
        except Exception as e:
            st, err = "failed", str(e)
            counts["failed"] += 1
        await record_message(kind="lookbook", campaign_id=campaign, lookbook_id=card_id,
                             branch_id=card["branch_id"], to=to, text=caption, status=st,
                             error=err, provider=provider.name, created_by=user.id)
    await log_event("whatsapp", "lookbook_broadcast", entity_id=campaign, user_id=user.id,
                    branch_id=card["branch_id"], diff={"recipients": len(numbers), **counts})
    return {"campaign_id": campaign, "recipients": len(numbers), "invalid_skipped": invalid,
            "mocked": provider.mocked, **counts}
