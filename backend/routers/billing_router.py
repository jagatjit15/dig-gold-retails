"""Billing counter: quote, GST bill (marks items sold), PDF invoice."""
import logging
import math
from typing import Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from db import db
from models import StockMovement, UserPublic, new_id, now_iso
from auth import get_current_user, require_roles, enforce_branch
from audit import log_event
from invoice_pdf import build_invoice_pdf
from whatsapp import send_invoice_message

router = APIRouter(prefix="/bills", tags=["billing"])
logger = logging.getLogger("swarnaerp.billing")
DEFAULT_GST = 3.0
MakingType = Literal["per_gram", "percent", "fixed"]


class MakingOverride(BaseModel):
    making_charge_type: MakingType
    making_charge_value: float = Field(ge=0)


class BillCreate(BaseModel):
    branch_id: str
    item_ids: List[str] = Field(min_length=1)
    customer_name: str = ""
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    customer_gstin: Optional[str] = None
    customer_state_code: Optional[str] = None
    payment_mode: Literal["cash", "card", "upi", "bank", "mixed"] = "cash"
    making_overrides: Dict[str, MakingOverride] = {}


class BillLine(BaseModel):
    item_id: str
    tag_id: str
    huid: Optional[str] = None
    hsn_code: Optional[str] = None
    purity_code: str
    gross_wt: float = 0
    stone_wt: float = 0
    net_wt: float
    rate_per_gram: float
    metal_value: float
    making_charge_type: str = "fixed"
    making_charge_value: float = 0
    making_charge: float
    taxable: float
    gst_rate: float = DEFAULT_GST


class Totals(BaseModel):
    lines: List[BillLine]
    subtotal: float
    cgst: float
    sgst: float
    igst: float = 0
    round_off: float = 0
    grand_total: float
    inter_state: bool = False


class Bill(Totals):
    id: str
    bill_no: str
    branch_id: str
    customer_name: str
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    customer_gstin: Optional[str] = None
    customer_state_code: Optional[str] = None
    payment_mode: str = "cash"
    whatsapp_status: Optional[str] = None
    created_by: str
    created_at: str


def _making(mtype: str, value: float, net_wt: float, metal_value: float) -> float:
    if mtype == "per_gram":
        return value * net_wt
    if mtype == "percent":
        return metal_value * value / 100
    return value


async def _price_lines(items: List[dict], overrides: Dict[str, MakingOverride]) -> List[BillLine]:
    purities = {p["id"]: p for p in await db.purities.find({}, {"_id": 0}).to_list(200)}
    cats = {c["id"]: c for c in await db.categories.find({}, {"_id": 0}).to_list(500)}
    lines = []
    for it in items:
        code = purities.get(it["purity_id"], {}).get("code")
        rate = await db.daily_rates.find_one({"purity_code": code}, {"_id": 0},
                                             sort=[("rate_date", -1), ("created_at", -1)])
        if not rate:
            raise HTTPException(400, f"No daily rate set for {code}")
        ov = overrides.get(it["id"])
        mtype = ov.making_charge_type if ov else it.get("making_charge_type", "fixed")
        mval = ov.making_charge_value if ov else (it.get("making_charge_value") or 0)
        metal = round(it["net_wt"] * rate["rate_per_gram"], 2)
        making = round(_making(mtype, mval, it["net_wt"], metal), 2)
        cat = cats.get(it["category_id"], {})
        lines.append(BillLine(
            item_id=it["id"], tag_id=it["tag_id"], huid=it.get("huid"),
            hsn_code=cat.get("hsn_code"), purity_code=code, gross_wt=it["gross_wt"],
            stone_wt=it.get("stone_wt", 0), net_wt=it["net_wt"],
            rate_per_gram=rate["rate_per_gram"], metal_value=metal,
            making_charge_type=mtype, making_charge_value=mval, making_charge=making,
            taxable=round(metal + making, 2), gst_rate=cat.get("gst_rate") or DEFAULT_GST))
    return lines


def _totals(lines: List[BillLine], branch_state: Optional[str],
            cust_state: Optional[str]) -> Totals:
    subtotal = round(sum(ln.taxable for ln in lines), 2)
    tax = round(sum(ln.taxable * ln.gst_rate / 100 for ln in lines), 2)
    inter = bool(cust_state and branch_state and cust_state != branch_state)
    cgst = 0 if inter else round(tax / 2, 2)
    sgst = 0 if inter else round(tax - cgst, 2)
    igst = tax if inter else 0
    exact = subtotal + cgst + sgst + igst
    grand = math.floor(exact + 0.5)
    return Totals(lines=lines, subtotal=subtotal, cgst=cgst, sgst=sgst, igst=igst,
                  round_off=round(grand - exact, 2), grand_total=float(grand),
                  inter_state=inter)


async def _compute(body: BillCreate, user: UserPublic):
    enforce_branch(user, body.branch_id)
    branch = await db.branches.find_one({"id": body.branch_id}, {"_id": 0})
    if not branch:
        raise HTTPException(404, "Branch not found")
    ids = list(dict.fromkeys(body.item_ids))
    items = await db.items.find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids))
    if len(items) != len(ids):
        raise HTTPException(404, "One or more items not found")
    for it in items:
        if it["branch_id"] != body.branch_id:
            raise HTTPException(400, f"{it['tag_id']} belongs to another branch")
        if it["status"] != "in_stock":
            raise HTTPException(409, f"{it['tag_id']} is not in stock ({it['status']})")
    lines = await _price_lines(items, body.making_overrides)
    return branch, items, _totals(lines, branch.get("state_code"), body.customer_state_code)


@router.post("/quote", response_model=Totals)
async def quote(body: BillCreate,
                user: UserPublic = Depends(require_roles("admin", "manager", "billing"))):
    return (await _compute(body, user))[2]


@router.post("", response_model=Bill)
async def create_bill(body: BillCreate,
                      user: UserPublic = Depends(require_roles("admin", "manager", "billing"))):
    if not body.customer_name.strip():
        raise HTTPException(400, "Customer name is required")
    branch, items, totals = await _compute(body, user)

    sold = []
    for it in items:
        res = await db.items.update_one({"id": it["id"], "status": "in_stock"},
                                        {"$set": {"status": "sold", "updated_at": now_iso()}})
        if res.modified_count == 0:
            await db.items.update_many({"id": {"$in": sold}}, {"$set": {"status": "in_stock"}})
            raise HTTPException(409, f"{it['tag_id']} was sold by someone else just now")
        sold.append(it["id"])

    counter = await db.counters.find_one_and_update(
        {"_id": f"bill:{body.branch_id}"}, {"$inc": {"seq": 1}},
        upsert=True, return_document=ReturnDocument.AFTER)
    bill = Bill(**totals.model_dump(), id=new_id(),
                bill_no=f"{branch['code']}-{counter['seq']:05d}", branch_id=body.branch_id,
                customer_name=body.customer_name.strip(), customer_phone=body.customer_phone,
                customer_address=body.customer_address, customer_gstin=body.customer_gstin,
                customer_state_code=body.customer_state_code, payment_mode=body.payment_mode,
                created_by=user.id, created_at=now_iso())
    await db.bills.insert_one(bill.model_dump())
    await db.stock_movements.insert_many([
        StockMovement(movement_type="sale", item_id=ln.item_id, weight=ln.net_wt,
                      branch_id=body.branch_id, reference=bill.bill_no,
                      user_id=user.id).model_dump() for ln in bill.lines])
    await log_event("bill", "create", entity_id=bill.id, user_id=user.id,
                    branch_id=body.branch_id,
                    diff={"bill_no": bill.bill_no, "items": [ln.tag_id for ln in bill.lines],
                          "grand_total": bill.grand_total})
    if bill.customer_phone:
        try:
            rec = await send_invoice_message(bill.model_dump(), branch, user.id)
            bill.whatsapp_status = rec["status"]
            await db.bills.update_one({"id": bill.id}, {"$set": {"whatsapp_status": rec["status"]}})
        except Exception:
            logger.exception("Auto WhatsApp failed for %s", bill.bill_no)
    return bill


@router.get("", response_model=List[Bill])
async def list_bills(branch_id: str, user: UserPublic = Depends(get_current_user)):
    enforce_branch(user, branch_id)
    docs = await db.bills.find({"branch_id": branch_id}, {"_id": 0}).sort(
        [("created_at", -1)]).to_list(200)
    return [Bill(**d) for d in docs]


@router.get("/{bill_id}/pdf")
async def bill_pdf(bill_id: str, user: UserPublic = Depends(get_current_user)):
    bill = await db.bills.find_one({"id": bill_id}, {"_id": 0})
    if not bill:
        raise HTTPException(404, "Bill not found")
    enforce_branch(user, bill["branch_id"])
    branch = await db.branches.find_one({"id": bill["branch_id"]}, {"_id": 0})
    pdf = build_invoice_pdf(Bill(**bill).model_dump(), branch)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{bill["bill_no"]}.pdf"'})
