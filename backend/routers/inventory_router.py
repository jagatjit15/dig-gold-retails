"""Inventory items + scan service + stock audit + stock movements."""
from fastapi import APIRouter, Depends, HTTPException
import re
from typing import List, Optional
from pydantic import BaseModel

from db import db
from models import (
    Item, ItemCreate,
    StockMovement, ScanLog, ScanRequest,
    AuditSession, AuditScan,
    UserPublic, now_iso,
)
from auth import get_current_user, enforce_branch, require_roles
from audit import log_event

router = APIRouter(tags=["inventory"])


# -------- Items --------

@router.get("/items", response_model=List[Item])
async def list_items(
    branch_id: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    user: UserPublic = Depends(get_current_user),
):
    query = {}
    if branch_id:
        enforce_branch(user, branch_id)
        query["branch_id"] = branch_id
    elif user.role != "admin" and user.branch_id:
        query["branch_id"] = user.branch_id
    if status:
        query["status"] = status
    if q:
        pattern = re.escape(q.strip()[:64])
        query["$or"] = [
            {"tag_id": {"$regex": pattern, "$options": "i"}},
            {"barcode": {"$regex": pattern, "$options": "i"}},
            {"rfid_epc": {"$regex": pattern, "$options": "i"}},
            {"huid": {"$regex": pattern, "$options": "i"}},
        ]
    docs = await db.items.find(query, {"_id": 0}).sort([("created_at", -1)]).to_list(500)
    return [Item(**d) for d in docs]


@router.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: str, user: UserPublic = Depends(get_current_user)):
    doc = await db.items.find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Item not found")
    enforce_branch(user, doc["branch_id"])
    return Item(**doc)


@router.post("/items", response_model=Item)
async def create_item(
    body: ItemCreate,
    user: UserPublic = Depends(require_roles("admin", "manager", "billing")),
):
    enforce_branch(user, body.branch_id)
    # Uniqueness checks
    for field, val in [("tag_id", body.tag_id), ("barcode", body.barcode),
                       ("rfid_epc", body.rfid_epc)]:
        if val:
            if await db.items.find_one({field: val}, {"_id": 0}):
                raise HTTPException(409, f"Duplicate {field}: {val}")
    net_wt = round(body.gross_wt - body.stone_wt, 3)
    if net_wt < 0:
        raise HTTPException(400, "Stone weight exceeds gross weight")
    item = Item(**body.model_dump(), net_wt=net_wt)
    await db.items.insert_one(item.model_dump())
    # append-only movement: receipt
    mv = StockMovement(
        movement_type="receipt",
        item_id=item.id,
        weight=item.net_wt,
        branch_id=item.branch_id,
        reference=f"NEW:{item.tag_id}",
        user_id=user.id,
    )
    await db.stock_movements.insert_one(mv.model_dump())
    await log_event("item", "create", entity_id=item.id, user_id=user.id,
                    branch_id=item.branch_id, diff=item.model_dump())
    return item


# -------- Scan service --------

@router.post("/scan", response_model=ScanLog)
async def scan(body: ScanRequest, user: UserPublic = Depends(get_current_user)):
    """Lookup an item by barcode, tag_id, rfid_epc, or huid."""
    code = body.code.strip()
    item_doc = await db.items.find_one(
        {"$or": [
            {"barcode": code},
            {"tag_id": code},
            {"rfid_epc": code},
            {"huid": code},
        ]},
        {"_id": 0},
    )
    if item_doc and user.role != "admin" and item_doc["branch_id"] != user.branch_id:
        item_doc = None
    log = ScanLog(
        code=code,
        code_type=body.code_type,
        item_id=item_doc["id"] if item_doc else None,
        found=bool(item_doc),
        branch_id=user.branch_id or (item_doc["branch_id"] if item_doc else ""),
        user_id=user.id,
        device_id=body.device_id,
        context=body.context,
    )
    await db.scan_logs.insert_one(log.model_dump())
    # cross-branch warning for RFID scans
    if item_doc and user.role != "admin" and user.branch_id and \
       item_doc["branch_id"] != user.branch_id:
        # still return the item, UI will flag it
        pass
    return log


class ScanLookupResponse(BaseModel):
    found: bool
    item: Optional[Item] = None
    warnings: List[str] = []


@router.get("/scan/lookup", response_model=ScanLookupResponse)
async def scan_lookup(code: str, user: UserPublic = Depends(get_current_user)):
    code = code.strip()
    item_doc = await db.items.find_one(
        {"$or": [
            {"barcode": code},
            {"tag_id": code},
            {"rfid_epc": code},
            {"huid": code},
        ]},
        {"_id": 0},
    )
    if not item_doc:
        return ScanLookupResponse(found=False, warnings=[f"No item found for '{code}'"])
    warnings = []
    if item_doc["status"] != "in_stock":
        warnings.append(f"Item status is {item_doc['status']}")
    if user.role != "admin" and user.branch_id and \
       item_doc["branch_id"] != user.branch_id:
        return ScanLookupResponse(found=False, warnings=["Item belongs to another branch"])
    return ScanLookupResponse(found=True, item=Item(**item_doc), warnings=warnings)


# -------- Stock movements / register --------

@router.get("/movements", response_model=List[StockMovement])
async def list_movements(
    branch_id: Optional[str] = None,
    item_id: Optional[str] = None,
    user: UserPublic = Depends(get_current_user),
):
    q = {}
    if branch_id:
        enforce_branch(user, branch_id)
        q["branch_id"] = branch_id
    elif user.role != "admin" and user.branch_id:
        q["branch_id"] = user.branch_id
    if item_id:
        q["item_id"] = item_id
    docs = await db.stock_movements.find(q, {"_id": 0}).sort(
        [("created_at", -1)]).to_list(1000)
    return [StockMovement(**d) for d in docs]


class StockSummary(BaseModel):
    branch_id: str
    total_items_in_stock: int
    total_net_weight: float
    by_purity: dict


@router.get("/stock/summary", response_model=StockSummary)
async def stock_summary(
    branch_id: str, user: UserPublic = Depends(get_current_user)
):
    enforce_branch(user, branch_id)
    pipeline = [
        {"$match": {"branch_id": branch_id, "status": "in_stock"}},
        {"$group": {
            "_id": "$purity_id",
            "count": {"$sum": 1},
            "net_wt": {"$sum": "$net_wt"},
        }},
    ]
    rows = await db.items.aggregate(pipeline).to_list(100)
    total_count = sum(r["count"] for r in rows)
    total_wt = round(sum(r["net_wt"] for r in rows), 3)
    by_purity = {r["_id"]: {"count": r["count"], "net_wt": round(r["net_wt"], 3)}
                 for r in rows}
    return StockSummary(
        branch_id=branch_id,
        total_items_in_stock=total_count,
        total_net_weight=total_wt,
        by_purity=by_purity,
    )


# -------- Audit sessions --------

@router.post("/audit/sessions", response_model=AuditSession)
async def start_audit(
    branch_id: str,
    scope: Optional[str] = None,
    user: UserPublic = Depends(require_roles("admin", "manager", "auditor")),
):
    enforce_branch(user, branch_id)
    s = AuditSession(branch_id=branch_id, started_by=user.id, scope=scope)
    await db.audit_sessions.insert_one(s.model_dump())
    await log_event("audit_session", "start", entity_id=s.id, user_id=user.id,
                    branch_id=branch_id)
    return s


@router.get("/audit/sessions", response_model=List[AuditSession])
async def list_audit_sessions(
    branch_id: Optional[str] = None,
    user: UserPublic = Depends(get_current_user),
):
    q = {}
    if branch_id:
        enforce_branch(user, branch_id)
        q["branch_id"] = branch_id
    elif user.role != "admin" and user.branch_id:
        q["branch_id"] = user.branch_id
    docs = await db.audit_sessions.find(q, {"_id": 0}).sort(
        [("started_at", -1)]).to_list(100)
    return [AuditSession(**d) for d in docs]


class AuditScanRequest(BaseModel):
    code: str


@router.post("/audit/sessions/{session_id}/scan", response_model=AuditScan)
async def audit_scan(
    session_id: str,
    body: AuditScanRequest,
    user: UserPublic = Depends(get_current_user),
):
    sess = await db.audit_sessions.find_one({"id": session_id}, {"_id": 0})
    if not sess:
        raise HTTPException(404, "Audit session not found")
    if sess["status"] != "open":
        raise HTTPException(400, "Audit session is closed")
    enforce_branch(user, sess["branch_id"])
    code = body.code.strip()
    item = await db.items.find_one(
        {"$or": [{"barcode": code}, {"tag_id": code}, {"rfid_epc": code},
                 {"huid": code}]},
        {"_id": 0},
    )
    if not item:
        status_val = "unknown"
        item_id = None
    elif item["branch_id"] != sess["branch_id"]:
        status_val = "wrong_branch"
        item_id = item["id"]
    elif item["status"] != "in_stock":
        status_val = "wrong_status"
        item_id = item["id"]
    else:
        status_val = "found"
        item_id = item["id"]
    scan = AuditScan(session_id=session_id, code=code, item_id=item_id,
                     status=status_val)
    await db.audit_scans.insert_one(scan.model_dump())
    return scan


class AuditVariance(BaseModel):
    session_id: str
    expected_count: int
    scanned_found: int
    missing: List[dict]
    unknown_codes: List[str]
    wrong_branch_items: List[dict]
    wrong_status_items: List[dict]


@router.get("/audit/sessions/{session_id}/variance",
            response_model=AuditVariance)
async def audit_variance(
    session_id: str, user: UserPublic = Depends(get_current_user)
):
    sess = await db.audit_sessions.find_one({"id": session_id}, {"_id": 0})
    if not sess:
        raise HTTPException(404, "Audit session not found")
    enforce_branch(user, sess["branch_id"])
    scans = await db.audit_scans.find({"session_id": session_id}, {"_id": 0}).to_list(5000)
    scanned_item_ids = {s["item_id"] for s in scans if s["status"] == "found"}
    expected = await db.items.find(
        {"branch_id": sess["branch_id"], "status": "in_stock"}, {"_id": 0}
    ).to_list(10000)
    expected_ids = {i["id"] for i in expected}
    missing = [i for i in expected if i["id"] not in scanned_item_ids]
    unknown = [s["code"] for s in scans if s["status"] == "unknown"]
    wrong_branch_ids = [s["item_id"] for s in scans if s["status"] == "wrong_branch"]
    wrong_status_ids = [s["item_id"] for s in scans if s["status"] == "wrong_status"]
    wrong_branch_items = await db.items.find(
        {"id": {"$in": wrong_branch_ids}}, {"_id": 0}
    ).to_list(500) if wrong_branch_ids else []
    wrong_status_items = await db.items.find(
        {"id": {"$in": wrong_status_ids}}, {"_id": 0}
    ).to_list(500) if wrong_status_ids else []
    return AuditVariance(
        session_id=session_id,
        expected_count=len(expected_ids),
        scanned_found=len(scanned_item_ids),
        missing=[{"id": i["id"], "tag_id": i["tag_id"], "net_wt": i["net_wt"]}
                 for i in missing],
        unknown_codes=unknown,
        wrong_branch_items=[{"id": i["id"], "tag_id": i["tag_id"],
                             "branch_id": i["branch_id"]} for i in wrong_branch_items],
        wrong_status_items=[{"id": i["id"], "tag_id": i["tag_id"],
                             "status": i["status"]} for i in wrong_status_items],
    )


@router.post("/audit/sessions/{session_id}/close", response_model=AuditSession)
async def close_audit(
    session_id: str,
    user: UserPublic = Depends(require_roles("admin", "manager", "auditor")),
):
    sess = await db.audit_sessions.find_one({"id": session_id}, {"_id": 0})
    if not sess:
        raise HTTPException(404, "Audit session not found")
    enforce_branch(user, sess["branch_id"])
    await db.audit_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "closed", "closed_at": now_iso()}},
    )
    await log_event("audit_session", "close", entity_id=session_id,
                    user_id=user.id, branch_id=sess["branch_id"])
    sess = await db.audit_sessions.find_one({"id": session_id}, {"_id": 0})
    return AuditSession(**sess)


# -------- Audit log viewer (RBAC) --------

@router.get("/audit-log")
async def read_audit_log(
    limit: int = 100,
    user: UserPublic = Depends(require_roles("admin", "manager", "auditor")),
):
    q = {} if user.role == "admin" else {"branch_id": user.branch_id}
    docs = await db.audit_log.find(q, {"_id": 0}).sort(
        [("created_at", -1)]).to_list(min(max(limit, 1), 500))
    return docs
