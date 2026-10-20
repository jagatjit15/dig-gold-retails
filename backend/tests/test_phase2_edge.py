# Phase 2 edge cases: large (<25MB) upload through ingress, concurrent double-sell race
import os
import uuid
import concurrent.futures as cf
import requests

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"


def _admin():
    t = requests.post(f"{API}/auth/login", json={"email": "admin@swarnaerp.in", "password": "Admin@12345"}).json()
    return {"Authorization": f"Bearer {t['access_token']}"}


def _masters(h):
    br = {b["code"]: b for b in requests.get(f"{API}/branches", headers=h).json()}
    pur = {p["code"]: p for p in requests.get(f"{API}/purities", headers=h).json()}
    cat = requests.get(f"{API}/categories", headers=h).json()[0]
    return br, pur, cat


def test_20mb_upload_ok():
    h = _admin()
    br, _, _ = _masters(h)
    data = os.urandom(20 * 1024 * 1024)
    r = requests.post(f"{API}/files", headers=h, data={"owner_type": "branch", "owner_id": br["ZB-MAIN"]["id"]},
                      files={"file": ("TEST_big.bin", data, "application/octet-stream")}, timeout=240)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    fid = r.json()["id"]
    d = requests.get(f"{API}/files/{fid}/download", headers=h, timeout=240)
    assert d.status_code == 200 and len(d.content) == len(data)
    requests.delete(f"{API}/files/{fid}", headers=h)


def test_concurrent_double_sell():
    h = _admin()
    br, pur, cat = _masters(h)
    tag = f"TEST-RACE-{uuid.uuid4().hex[:6].upper()}"
    it = requests.post(f"{API}/items", headers=h, json={
        "tag_id": tag, "category_id": cat["id"], "purity_id": pur["22K916"]["id"],
        "gross_wt": 5, "stone_wt": 0, "branch_id": br["ZB-MAIN"]["id"]}).json()
    body = {"branch_id": br["ZB-MAIN"]["id"], "item_ids": [it["id"]], "customer_name": "TEST race"}
    with cf.ThreadPoolExecutor(5) as ex:
        codes = list(ex.map(lambda _: requests.post(f"{API}/bills", headers=h, json=body).status_code, range(5)))
    assert codes.count(200) == 1 and codes.count(409) == 4, codes
