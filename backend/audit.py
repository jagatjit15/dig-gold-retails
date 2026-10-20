"""Append-only hash-chained audit log."""
from __future__ import annotations
import hashlib
import json
from typing import Optional
from db import db
from models import AuditLogEntry, now_iso


def _hash_entry(entry: dict, prev_hash: Optional[str]) -> str:
    canonical = {
        "id": entry["id"],
        "entity": entry["entity"],
        "entity_id": entry.get("entity_id"),
        "action": entry["action"],
        "user_id": entry.get("user_id"),
        "branch_id": entry.get("branch_id"),
        "diff": entry.get("diff"),
        "created_at": entry["created_at"],
        "prev_hash": prev_hash,
    }
    payload = json.dumps(canonical, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def log_event(
    entity: str,
    action: str,
    *,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    diff: Optional[dict] = None,
):
    last = await db.audit_log.find_one(
        {}, {"_id": 0, "hash": 1}, sort=[("created_at", -1)]
    )
    prev_hash = last.get("hash") if last else None
    entry = AuditLogEntry(
        entity=entity,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        branch_id=branch_id,
        diff=diff,
        created_at=now_iso(),
        prev_hash=prev_hash,
    ).model_dump()
    entry["hash"] = _hash_entry(entry, prev_hash)
    await db.audit_log.insert_one(entry)
    entry.pop("_id", None)
    return entry
