"""Branch stock transfers: draft -> scan-out -> dispatch (in transit) -> scan-in -> receive."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import ReturnDocument

from db import db
from models import StockMovement, UserPublic, new_id, now_iso
from auth import get_current_user, require_roles, enforce_branch
from audit import log_event

router = APIRouter(prefix="/transfers", tags=["transfers"])
OPEN = ["draft", "in_transit"]
managers = require_roles("admin", "manager")


class TransferCreate(BaseModel):
    from_branch_id: str
    to_branch_id: str
    notes: Optional[str] = None


class CodeIn(BaseModel):
    code: str


class TransferItem(BaseModel):
    item_id: str
    tag_id: str
    net_wt: float
    received: bool = False


class Transfer(BaseModel):
    id: str
    transfer_no: str
    from_branch_id: str
    to_branch_id: str
    status: str
    notes: Optional[str] = None
    items: List[TransferItem] = []
    unexpected_codes: List[str] = []
    missing_item_ids: List[str] = []
    created_by: str
    created_at: str
    dispatched_at: Optional[str] = None
    received_at: Optional[str] = None
    received_by: Optional[str] = None


async def _get(tid: str) -> dict:
    t = await db.transfers.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Transfer not found")
    return t


async def _find_item(code: str) -> dict:
    code = code.strip()
    item = await db.items.find_one({"$or": [{"barcode": code}, {"tag_id": code},
                                            {"rfid_epc": code}, {"huid": code}]}, {"_id": 0})
    return item


@router.post("", response_model=Transfer)
async def create_transfer(body: TransferCreate, user: UserPublic = Depends(managers)):
    enforce_branch(user, body.from_branch_id)
    if body.from_branch_id == body.to_branch_id:
        raise HTTPException(400, "Choose a different destination branch")
    src = await db.branches.find_one({"id": body.from_branch_id}, {"_id": 0})
    if not src or not await db.branches.find_one({"id": body.to_branch_id}, {"_id": 0, "id": 1}):
        raise HTTPException(404, "Branch not found")
    counter = await db.counters.find_one_and_update(
        {"_id": f"transfer:{body.from_branch_id}"}, {"$inc": {"seq": 1}},
        upsert=True, return_document=ReturnDocument.AFTER)
    t = Transfer(id=new_id(), transfer_no=f"TR-{src['code']}-{counter['seq']:04d}",
                 from_branch_id=body.from_branch_id, to_branch_id=body.to_branch_id,
                 status="draft", notes=body.notes, created_by=user.id, created_at=now_iso())
    await db.transfers.insert_one(t.model_dump())
    await log_event("transfer", "create", entity_id=t.id, user_id=user.id,
                    branch_id=body.from_branch_id, diff={"to": body.to_branch_id})
    return t


@router.get("", response_model=List[Transfer])
async def list_transfers(branch_id: str, user: UserPublic = Depends(get_current_user)):
    enforce_branch(user, branch_id)
    docs = await db.transfers.find(
        {"$or": [{"from_branch_id": branch_id}, {"to_branch_id": branch_id}]}, {"_id": 0}
    ).sort([("created_at", -1)]).to_list(200)
    return [Transfer(**d) for d in docs]


@router.get("/branches")
async def destination_branches(_: UserPublic = Depends(get_current_user)):
    return await db.branches.find({"active": {"$ne": False}},
                                  {"_id": 0, "id": 1, "code": 1, "name": 1}).to_list(500)


@router.get("/{tid}", response_model=Transfer)
async def get_transfer(tid: str, user: UserPublic = Depends(get_current_user)):
    t = await _get(tid)
    if user.role != "admin" and user.branch_id not in (t["from_branch_id"], t["to_branch_id"]):
        raise HTTPException(403, "Branch scope violation")
    return Transfer(**t)


@router.post("/{tid}/scan-out", response_model=Transfer)
async def scan_out(tid: str, body: CodeIn, user: UserPublic = Depends(managers)):
    t = await _get(tid)
    enforce_branch(user, t["from_branch_id"])
    if t["status"] != "draft":
        raise HTTPException(400, "Items can only be added before dispatch")
    item = await _find_item(body.code)
    if not item:
        raise HTTPException(404, f"No item for '{body.code.strip()}'")
    if item["branch_id"] != t["from_branch_id"]:
        raise HTTPException(400, f"{item['tag_id']} belongs to another branch")
    if item["status"] != "in_stock":
        raise HTTPException(409, f"{item['tag_id']} is {item['status'].replace('_', ' ')}")
    if any(i["item_id"] == item["id"] for i in t["items"]):
        raise HTTPException(409, f"{item['tag_id']} is already on this transfer")
    other = await db.transfers.find_one({"id": {"$ne": tid}, "status": "draft",
                                         "items.item_id": item["id"]}, {"_id": 0, "transfer_no": 1})
    if other:
        raise HTTPException(409, f"{item['tag_id']} is already on transfer {other['transfer_no']}")
    line = TransferItem(item_id=item["id"], tag_id=item["tag_id"], net_wt=item["net_wt"])
    await db.transfers.update_one({"id": tid}, {"$push": {"items": line.model_dump()}})
    return Transfer(**await _get(tid))


@router.delete("/{tid}/items/{item_id}", response_model=Transfer)
async def remove_item(tid: str, item_id: str, user: UserPublic = Depends(managers)):
    t = await _get(tid)
    enforce_branch(user, t["from_branch_id"])
    if t["status"] != "draft":
        raise HTTPException(400, "Items can only be removed before dispatch")
    await db.transfers.update_one({"id": tid}, {"$pull": {"items": {"item_id": item_id}}})
    return Transfer(**await _get(tid))


@router.post("/{tid}/dispatch", response_model=Transfer)
async def dispatch(tid: str, user: UserPublic = Depends(managers)):
    t = await _get(tid)
    enforce_branch(user, t["from_branch_id"])
    if t["status"] != "draft":
        raise HTTPException(400, "Transfer already dispatched")
    if not t["items"]:
        raise HTTPException(400, "Scan at least one item before dispatch")
    done = []
    for line in t["items"]:
        res = await db.items.update_one(
            {"id": line["item_id"], "status": "in_stock", "branch_id": t["from_branch_id"]},
            {"$set": {"status": "in_transit", "updated_at": now_iso()}})
        if res.modified_count == 0:
            await db.items.update_many({"id": {"$in": done}}, {"$set": {"status": "in_stock"}})
            raise HTTPException(409, f"{line['tag_id']} is no longer in stock — remove it and retry")
        done.append(line["item_id"])
    await db.stock_movements.insert_many([
        StockMovement(movement_type="transfer_out", item_id=line["item_id"], weight=line["net_wt"],
                      branch_id=t["from_branch_id"], reference=t["transfer_no"],
                      user_id=user.id).model_dump() for line in t["items"]])
    await db.transfers.update_one({"id": tid}, {"$set": {"status": "in_transit",
                                                         "dispatched_at": now_iso()}})
    await log_event("transfer", "dispatch", entity_id=tid, user_id=user.id,
                    branch_id=t["from_branch_id"], diff={"items": len(t["items"])})
    return Transfer(**await _get(tid))


@router.post("/{tid}/scan-in", response_model=Transfer)
async def scan_in(tid: str, body: CodeIn, user: UserPublic = Depends(managers)):
    t = await _get(tid)
    enforce_branch(user, t["to_branch_id"])
    if t["status"] != "in_transit":
        raise HTTPException(400, "Transfer is not in transit")
    code = body.code.strip()
    item = await _find_item(code)
    line = item and next((i for i in t["items"] if i["item_id"] == item["id"]), None)
    if not line:
        if code not in t["unexpected_codes"]:
            await db.transfers.update_one({"id": tid}, {"$push": {"unexpected_codes": code}})
        raise HTTPException(404, f"'{code}' is not on this transfer")
    await db.transfers.update_one({"id": tid, "items.item_id": item["id"]},
                                  {"$set": {"items.$.received": True}})
    return Transfer(**await _get(tid))


@router.post("/{tid}/receive", response_model=Transfer)
async def receive(tid: str, user: UserPublic = Depends(managers)):
    t = await _get(tid)
    enforce_branch(user, t["to_branch_id"])
    if t["status"] != "in_transit":
        raise HTTPException(400, "Transfer is not in transit")
    got = [i for i in t["items"] if i["received"]]
    missing = [i["item_id"] for i in t["items"] if not i["received"]]
    if not got:
        raise HTTPException(400, "Scan in at least one item before receiving")
    await db.items.update_many({"id": {"$in": [i["item_id"] for i in got]}, "status": "in_transit"},
                               {"$set": {"status": "in_stock", "branch_id": t["to_branch_id"],
                                         "updated_at": now_iso()}})
    await db.stock_movements.insert_many([
        StockMovement(movement_type="transfer_in", item_id=i["item_id"], weight=i["net_wt"],
                      branch_id=t["to_branch_id"], reference=t["transfer_no"],
                      user_id=user.id).model_dump() for i in got])
    status = "received_with_variance" if missing else "received"
    await db.transfers.update_one({"id": tid}, {"$set": {
        "status": status, "missing_item_ids": missing,
        "received_at": now_iso(), "received_by": user.id}})
    await log_event("transfer", "receive", entity_id=tid, user_id=user.id,
                    branch_id=t["to_branch_id"],
                    diff={"received": len(got), "missing": len(missing)})
    return Transfer(**await _get(tid))


@router.post("/{tid}/cancel", response_model=Transfer)
async def cancel(tid: str, user: UserPublic = Depends(managers)):
    t = await _get(tid)
    enforce_branch(user, t["from_branch_id"])
    if t["status"] != "draft":
        raise HTTPException(400, "Only draft transfers can be cancelled")
    await db.transfers.update_one({"id": tid}, {"$set": {"status": "cancelled"}})
    await log_event("transfer", "cancel", entity_id=tid, user_id=user.id,
                    branch_id=t["from_branch_id"])
    return Transfer(**await _get(tid))
