"""Pydantic models for the Jewellery ERP."""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional, List
import uuid
from pydantic import BaseModel, Field, ConfigDict, EmailStr


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# ---------------- Auth / Users ----------------

Role = Literal["admin", "manager", "billing", "auditor"]


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: Role = "billing"
    branch_id: Optional[str] = None  # None => allowed all branches (admin)


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: Role
    branch_id: Optional[str] = None
    active: bool = True
    created_at: str


class UserInDB(UserPublic):
    model_config = ConfigDict(extra="ignore")
    password_hash: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    user: UserPublic


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------- Masters ----------------


class Branch(BaseModel):
    id: str = Field(default_factory=new_id)
    code: str
    name: str
    address: Optional[str] = None
    gstin: Optional[str] = None
    state_code: Optional[str] = None  # for intra/inter-state logic
    active: bool = True
    created_at: str = Field(default_factory=now_iso)


class BranchCreate(BaseModel):
    code: str
    name: str
    address: Optional[str] = None
    gstin: Optional[str] = None
    state_code: Optional[str] = None


class Purity(BaseModel):
    id: str = Field(default_factory=new_id)
    code: str  # e.g. 22K916
    label: str  # 22K Gold (91.6%)
    metal: Literal["gold", "silver", "platinum"]
    fineness: float  # 0.916 for 22K
    active: bool = True


class PurityCreate(BaseModel):
    code: str
    label: str
    metal: Literal["gold", "silver", "platinum"]
    fineness: float


class Category(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    hsn_code: Optional[str] = None
    gst_rate: Optional[float] = None  # percent, e.g. 3.0
    active: bool = True


class CategoryCreate(BaseModel):
    name: str
    hsn_code: Optional[str] = None
    gst_rate: Optional[float] = None


class DailyRate(BaseModel):
    id: str = Field(default_factory=new_id)
    rate_date: str  # ISO date (yyyy-mm-dd)
    metal: Literal["gold", "silver", "platinum"]
    purity_code: str  # e.g. 24K, 22K916, 925
    rate_per_gram: float  # INR
    set_by: Optional[str] = None  # user id
    created_at: str = Field(default_factory=now_iso)


class DailyRateCreate(BaseModel):
    rate_date: str
    metal: Literal["gold", "silver", "platinum"]
    purity_code: str
    rate_per_gram: float


# ---------------- Inventory ----------------

ItemStatus = Literal[
    "in_stock",
    "sold",
    "transferred",
    "in_transit",
    "with_karigar",
    "scrapped",
]
MakingChargeType = Literal["per_gram", "percent", "fixed"]


class Item(BaseModel):
    id: str = Field(default_factory=new_id)
    tag_id: str  # user-visible item code, must be unique
    barcode: Optional[str] = None
    rfid_epc: Optional[str] = None
    category_id: str
    purity_id: str
    gross_wt: float  # grams (3 decimals)
    stone_wt: float = 0.0
    net_wt: float
    making_charge_type: MakingChargeType = "per_gram"
    making_charge_value: float = 0.0
    huid: Optional[str] = None
    status: ItemStatus = "in_stock"
    branch_id: str
    description: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class ItemCreate(BaseModel):
    tag_id: str
    barcode: Optional[str] = None
    rfid_epc: Optional[str] = None
    category_id: str
    purity_id: str
    gross_wt: float
    stone_wt: float = 0.0
    making_charge_type: MakingChargeType = "per_gram"
    making_charge_value: float = 0.0
    huid: Optional[str] = None
    branch_id: str
    description: Optional[str] = None


# Stock movement - append-only ledger
MovementType = Literal[
    "receipt",  # new stock in
    "sale",
    "transfer_out",
    "transfer_in",
    "karigar_issue",
    "karigar_return",
    "scrap",
    "adjustment",  # requires manager approval + reason
    "audit_variance",
]


class StockMovement(BaseModel):
    id: str = Field(default_factory=new_id)
    movement_type: MovementType
    item_id: Optional[str] = None  # tagged item
    loose_lot_id: Optional[str] = None  # loose metal lot
    weight: float
    branch_id: str
    reference: Optional[str] = None  # doc number
    reason: Optional[str] = None
    user_id: str
    device_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class StockMovementCreate(BaseModel):
    movement_type: MovementType
    item_id: Optional[str] = None
    loose_lot_id: Optional[str] = None
    weight: float
    branch_id: str
    reference: Optional[str] = None
    reason: Optional[str] = None


# ---------------- Scan / Audit ----------------


class ScanLog(BaseModel):
    id: str = Field(default_factory=new_id)
    code: str  # raw scanned code
    code_type: Literal["barcode", "rfid", "manual"] = "barcode"
    item_id: Optional[str] = None
    found: bool
    branch_id: str
    user_id: str
    device_id: Optional[str] = None
    context: Optional[str] = None  # 'billing', 'audit', 'lookup'
    created_at: str = Field(default_factory=now_iso)


class ScanRequest(BaseModel):
    code: str
    code_type: Literal["barcode", "rfid", "manual"] = "barcode"
    context: Optional[str] = "lookup"
    device_id: Optional[str] = None


class AuditSession(BaseModel):
    id: str = Field(default_factory=new_id)
    branch_id: str
    started_by: str
    started_at: str = Field(default_factory=now_iso)
    closed_at: Optional[str] = None
    status: Literal["open", "closed", "approved"] = "open"
    scope: Optional[str] = None  # Tray/Counter/Safe filter


class AuditScan(BaseModel):
    id: str = Field(default_factory=new_id)
    session_id: str
    code: str
    item_id: Optional[str] = None
    status: Literal["found", "unknown", "wrong_branch", "wrong_status"]
    created_at: str = Field(default_factory=now_iso)


# ---------------- Audit log (hash chained) ----------------


class AuditLogEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    entity: str
    entity_id: Optional[str] = None
    action: str  # create/update/delete/login/scan
    user_id: Optional[str] = None
    branch_id: Optional[str] = None
    diff: Optional[dict] = None
    created_at: str = Field(default_factory=now_iso)
    prev_hash: Optional[str] = None
    hash: Optional[str] = None
