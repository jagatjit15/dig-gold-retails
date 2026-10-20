"""Emergent Object Storage client."""
import os
import requests

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "swarnaerp"
_storage_key = None


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init",
                         json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _request(method: str, path: str, **kw):
    extra = kw.pop("headers", {})
    for attempt in range(2):
        resp = requests.request(method, f"{STORAGE_URL}/objects/{path}",
                                headers={"X-Storage-Key": init_storage(force=attempt == 1),
                                         **extra}, **kw)
        if resp.status_code != 404:
            break
    resp.raise_for_status()
    return resp


def put_object(path: str, data: bytes, content_type: str) -> dict:
    return _request("PUT", path, headers={"Content-Type": content_type},
                    data=data, timeout=120).json()


def get_object(path: str):
    resp = _request("GET", path, timeout=60)
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
