"""File & media attachments: per item and per-branch document library."""
import asyncio
import re
import uuid
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from db import db
from models import UserPublic, now_iso
from auth import get_current_user, require_roles, enforce_branch
from audit import log_event
from storage import APP_NAME, put_object, get_object

router = APIRouter(prefix="/files", tags=["files"])
MAX_BYTES = 25 * 1024 * 1024
INLINE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif", "application/pdf"}


class FileRecord(BaseModel):
    id: str
    owner_type: Literal["item", "branch"]
    owner_id: str
    branch_id: str
    category: Optional[str] = None
    original_filename: str
    content_type: str
    size: int
    uploaded_by: str
    created_at: str


async def _owner_branch(owner_type: str, owner_id: str) -> str:
    if owner_type == "item":
        item = await db.items.find_one({"id": owner_id}, {"_id": 0, "branch_id": 1})
        if not item:
            raise HTTPException(404, "Item not found")
        return item["branch_id"]
    if not await db.branches.find_one({"id": owner_id}, {"_id": 0, "id": 1}):
        raise HTTPException(404, "Branch not found")
    return owner_id


@router.post("", response_model=FileRecord)
async def upload_file(
    owner_type: Literal["item", "branch"] = Form(...),
    owner_id: str = Form(...),
    category: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user: UserPublic = Depends(require_roles("admin", "manager", "billing")),
):
    branch_id = await _owner_branch(owner_type, owner_id)
    enforce_branch(user, branch_id)
    if file.size is not None and file.size > MAX_BYTES:
        raise HTTPException(413, "File exceeds 25 MB")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File exceeds 25 MB")
    name = file.filename or "file"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "bin"
    content_type = file.content_type or "application/octet-stream"
    path = f"{APP_NAME}/{owner_type}/{owner_id}/{uuid.uuid4()}.{ext}"
    try:
        result = await asyncio.to_thread(put_object, path, data, content_type)
    except Exception as e:
        raise HTTPException(502, f"Storage upload failed: {e}")
    rec = FileRecord(
        id=str(uuid.uuid4()), owner_type=owner_type, owner_id=owner_id,
        branch_id=branch_id, category=category, original_filename=name,
        content_type=content_type, size=result.get("size", len(data)),
        uploaded_by=user.id, created_at=now_iso(),
    )
    await db.files.insert_one({**rec.model_dump(), "storage_path": result["path"],
                               "is_deleted": False})
    await log_event("file", "upload", entity_id=rec.id, user_id=user.id,
                    branch_id=branch_id, diff={"name": name, "owner": f"{owner_type}:{owner_id}"})
    return rec


@router.get("", response_model=List[FileRecord])
async def list_files(owner_type: Literal["item", "branch"], owner_id: str,
                     user: UserPublic = Depends(get_current_user)):
    enforce_branch(user, await _owner_branch(owner_type, owner_id))
    docs = await db.files.find(
        {"owner_type": owner_type, "owner_id": owner_id, "is_deleted": False},
        {"_id": 0, "storage_path": 0, "is_deleted": 0},
    ).sort([("created_at", -1)]).to_list(500)
    return [FileRecord(**d) for d in docs]


async def _get_record(file_id: str, user: UserPublic) -> dict:
    rec = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "File not found")
    enforce_branch(user, rec["branch_id"])
    return rec


@router.get("/{file_id}/download")
async def download_file(file_id: str, user: UserPublic = Depends(get_current_user)):
    rec = await _get_record(file_id, user)
    try:
        data, _ = await asyncio.to_thread(get_object, rec["storage_path"])
    except Exception as e:
        raise HTTPException(502, f"Storage download failed: {e}")
    safe = re.sub(r'[^\w.\- ]', "_", rec["original_filename"])[:120] or "file"
    ctype = rec["content_type"].split(";")[0].strip().lower()
    inline = ctype in INLINE_TYPES
    return Response(content=data, media_type=ctype if inline else "application/octet-stream",
                    headers={"Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{safe}"',
                             "X-Content-Type-Options": "nosniff",
                             "Content-Security-Policy": "default-src 'none'; sandbox"})


@router.delete("/{file_id}")
async def delete_file(file_id: str,
                      user: UserPublic = Depends(require_roles("admin", "manager"))):
    rec = await _get_record(file_id, user)
    await db.files.update_one({"id": file_id}, {"$set": {"is_deleted": True,
                                                         "deleted_at": now_iso(),
                                                         "deleted_by": user.id}})
    await log_event("file", "delete", entity_id=file_id, user_id=user.id,
                    branch_id=rec["branch_id"], diff={"name": rec["original_filename"]})
    return {"ok": True}
