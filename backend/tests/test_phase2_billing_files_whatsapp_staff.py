# Phase 2 regression: files (object storage), billing/GST, WhatsApp mock, staff/auth, branch scoping
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("admin@swarnaerp.in", "Admin@12345")
BLR = ("counter.blr@swarnaerp.in", "Counter@123")
MGR = ("manager.zb@swarnaerp.in", "Manager@123")
RUN = uuid.uuid4().hex[:6].upper()


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def admin():
    return H(login(*ADMIN)["access_token"])


@pytest.fixture(scope="session")
def blr():
    return H(login(*BLR)["access_token"])


@pytest.fixture(scope="session")
def mgr():
    return H(login(*MGR)["access_token"])


@pytest.fixture(scope="session")
def masters(admin):
    br = {b["code"]: b for b in requests.get(f"{API}/branches", headers=admin).json()}
    pur = {p["code"]: p for p in requests.get(f"{API}/purities", headers=admin).json()}
    cats = requests.get(f"{API}/categories", headers=admin).json()
    rates = {r["purity_code"]: r["rate_per_gram"]
             for r in requests.get(f"{API}/daily-rates/latest", headers=admin).json()}
    return {"br": br, "pur": pur, "cat": cats[0], "rates": rates}


def make_item(admin, masters, branch="ZB-MAIN", mtype="per_gram", mval=500.0, gross=10.0, stone=1.0):
    tag = f"TEST-{RUN}-{uuid.uuid4().hex[:5].upper()}"
    r = requests.post(f"{API}/items", headers=admin, json={
        "tag_id": tag, "category_id": masters["cat"]["id"], "purity_id": masters["pur"]["22K916"]["id"],
        "gross_wt": gross, "stone_wt": stone, "making_charge_type": mtype, "making_charge_value": mval,
        "branch_id": masters["br"][branch]["id"]})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def zb_billing(admin, masters):
    email = f"test_billzb_{RUN.lower()}@swarnaerp.in"
    r = requests.post(f"{API}/auth/users", headers=admin, json={
        "email": email, "name": "TEST ZB biller", "password": "Billing@123",
        "role": "billing", "branch_id": masters["br"]["ZB-MAIN"]["id"]})
    assert r.status_code == 200, r.text
    return {"user": r.json(), "h": H(login(email, "Billing@123")["access_token"]), "email": email}


# ---------- Files ----------
class TestFiles:
    def test_upload_list_download_delete(self, admin, masters, zb_billing):
        item = make_item(admin, masters)
        payload = b"hello-swarna-" + RUN.encode() + os.urandom(64)
        r = requests.post(f"{API}/files", headers=zb_billing["h"],
                          data={"owner_type": "item", "owner_id": item["id"], "category": "photo"},
                          files={"file": ("ring.bin", payload, "application/octet-stream")})
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["size"] == len(payload) and rec["original_filename"] == "ring.bin"
        lst = requests.get(f"{API}/files", headers=admin,
                           params={"owner_type": "item", "owner_id": item["id"]}).json()
        assert any(f["id"] == rec["id"] for f in lst)
        d = requests.get(f"{API}/files/{rec['id']}/download", headers=admin)
        assert d.status_code == 200 and d.content == payload
        # billing cannot delete
        assert requests.delete(f"{API}/files/{rec['id']}", headers=zb_billing["h"]).status_code == 403
        assert requests.delete(f"{API}/files/{rec['id']}", headers=admin).status_code == 200
        lst = requests.get(f"{API}/files", headers=admin,
                           params={"owner_type": "item", "owner_id": item["id"]}).json()
        assert not any(f["id"] == rec["id"] for f in lst)
        assert requests.get(f"{API}/files/{rec['id']}/download", headers=admin).status_code == 404

    def test_branch_library_and_scope(self, admin, blr, mgr, masters):
        zb = masters["br"]["ZB-MAIN"]["id"]
        r = requests.post(f"{API}/files", headers=mgr, data={"owner_type": "branch", "owner_id": zb},
                          files={"file": ("doc.txt", b"branch doc", "text/plain")})
        assert r.status_code == 200, r.text
        assert requests.get(f"{API}/files", headers=blr,
                            params={"owner_type": "branch", "owner_id": zb}).status_code == 403
        assert requests.post(f"{API}/files", headers=blr, data={"owner_type": "branch", "owner_id": zb},
                             files={"file": ("x.txt", b"x", "text/plain")}).status_code == 403
        assert requests.get(f"{API}/files/{r.json()['id']}/download", headers=blr).status_code == 403
        assert requests.delete(f"{API}/files/{r.json()['id']}", headers=mgr).status_code == 200

    def test_over_25mb_rejected(self, admin, masters):
        zb = masters["br"]["ZB-MAIN"]["id"]
        big = b"0" * (25 * 1024 * 1024 + 10)
        r = requests.post(f"{API}/files", headers=admin, data={"owner_type": "branch", "owner_id": zb},
                          files={"file": ("big.bin", big, "application/octet-stream")}, timeout=180)
        assert r.status_code == 413, f"{r.status_code} {r.text[:200]}"


# ---------- Billing ----------
class TestBilling:
    def test_quote_intra_state(self, admin, masters):
        it = make_item(admin, masters, mtype="per_gram", mval=500, gross=10, stone=1)
        rate = masters["rates"]["22K916"]
        r = requests.post(f"{API}/bills/quote", headers=admin, json={
            "branch_id": masters["br"]["ZB-MAIN"]["id"], "item_ids": [it["id"]]})
        assert r.status_code == 200, r.text
        q = r.json()
        ln = q["lines"][0]
        assert ln["net_wt"] == 9.0
        assert abs(ln["metal_value"] - round(9 * rate, 2)) < 0.01
        assert abs(ln["making_charge"] - 4500) < 0.01
        tax = (ln["metal_value"] + 4500) * 0.03
        assert abs(q["cgst"] + q["sgst"] - tax) < 0.02 and abs(q["cgst"] - tax / 2) < 0.02
        assert q["igst"] == 0 and q["inter_state"] is False
        assert q["grand_total"] == int(q["grand_total"])
        assert abs(q["subtotal"] + q["cgst"] + q["sgst"] + q["round_off"] - q["grand_total"]) < 0.011

    def test_quote_igst_and_overrides(self, admin, masters):
        it = make_item(admin, masters)
        r = requests.post(f"{API}/bills/quote", headers=admin, json={
            "branch_id": masters["br"]["ZB-MAIN"]["id"], "item_ids": [it["id"]],
            "customer_state_code": "29",
            "making_overrides": {it["id"]: {"making_charge_type": "percent", "making_charge_value": 10}}})
        q = r.json()
        ln = q["lines"][0]
        assert abs(ln["making_charge"] - round(ln["metal_value"] * 0.1, 2)) < 0.01
        assert q["inter_state"] is True and q["cgst"] == 0 and q["sgst"] == 0
        assert abs(q["igst"] - ln["taxable"] * 0.03) < 0.02
        r = requests.post(f"{API}/bills/quote", headers=admin, json={
            "branch_id": masters["br"]["ZB-MAIN"]["id"], "item_ids": [it["id"]],
            "making_overrides": {it["id"]: {"making_charge_type": "fixed", "making_charge_value": 1234}}})
        assert r.json()["lines"][0]["making_charge"] == 1234

    def test_create_bill_marks_sold_and_movements(self, admin, masters):
        zb = masters["br"]["ZB-MAIN"]["id"]
        it = make_item(admin, masters)
        assert requests.post(f"{API}/bills", headers=admin, json={
            "branch_id": zb, "item_ids": [it["id"]]}).status_code == 400  # name required
        r = requests.post(f"{API}/bills", headers=admin, json={
            "branch_id": zb, "item_ids": [it["id"]], "customer_name": "TEST Cust",
            "customer_phone": "9876543210"})
        assert r.status_code == 200, r.text
        bill = r.json()
        assert bill["bill_no"].startswith("ZB-MAIN-") and len(bill["bill_no"].split("-")[-1]) == 5
        assert bill["whatsapp_status"] == "mocked"
        item = requests.get(f"{API}/items/{it['id']}", headers=admin).json()
        assert item["status"] == "sold"
        mv = requests.get(f"{API}/movements", headers=admin, params={"item_id": it["id"]}).json()
        assert any(m["movement_type"] == "sale" and m["reference"] == bill["bill_no"] for m in mv)
        # selling twice
        r2 = requests.post(f"{API}/bills", headers=admin, json={
            "branch_id": zb, "item_ids": [it["id"]], "customer_name": "TEST again"})
        assert r2.status_code == 409
        pdf = requests.get(f"{API}/bills/{bill['id']}/pdf", headers=admin)
        assert pdf.status_code == 200 and pdf.headers["content-type"].startswith("application/pdf")
        assert pdf.content[:4] == b"%PDF"
        bills = requests.get(f"{API}/bills", headers=admin, params={"branch_id": zb}).json()
        assert any(b["id"] == bill["id"] for b in bills)
        # whatsapp auto message
        msgs = requests.get(f"{API}/whatsapp/messages", headers=admin,
                            params={"branch_id": zb, "kind": "invoice"}).json()
        assert any(m.get("bill_id") == bill["id"] and m["status"] == "mocked" for m in msgs)
        rs = requests.post(f"{API}/whatsapp/invoices/{bill['id']}", headers=admin)
        assert rs.status_code == 200 and rs.json()["status"] == "mocked"
        TestBilling.bill = bill

    def test_other_branch_item_rejected(self, admin, masters):
        it = make_item(admin, masters, branch="MG-BLR")
        r = requests.post(f"{API}/bills", headers=admin, json={
            "branch_id": masters["br"]["ZB-MAIN"]["id"], "item_ids": [it["id"]], "customer_name": "X"})
        assert r.status_code in (400, 403)

    def test_blr_cannot_access_zb(self, blr, admin, masters):
        zb = masters["br"]["ZB-MAIN"]["id"]
        it = make_item(admin, masters)
        assert requests.post(f"{API}/bills/quote", headers=blr, json={
            "branch_id": zb, "item_ids": [it["id"]]}).status_code == 403
        assert requests.get(f"{API}/bills", headers=blr, params={"branch_id": zb}).status_code == 403
        assert requests.get(f"{API}/items", headers=blr, params={"branch_id": zb}).status_code == 403
        if getattr(TestBilling, "bill", None):
            assert requests.get(f"{API}/bills/{TestBilling.bill['id']}/pdf", headers=blr).status_code == 403
        lk = requests.get(f"{API}/scan/lookup", headers=blr, params={"code": it["tag_id"]}).json()
        assert lk["found"] is False and "Item belongs to another branch" in lk["warnings"]
        brs = requests.get(f"{API}/branches", headers=blr).json()
        assert [b["code"] for b in brs] == ["MG-BLR"]


# ---------- WhatsApp ----------
class TestWhatsApp:
    def test_status(self, admin):
        s = requests.get(f"{API}/whatsapp/status", headers=admin).json()
        assert s == {"provider": "mock", "mocked": True}

    def test_broadcast(self, admin, mgr, zb_billing, masters):
        zb = masters["br"]["ZB-MAIN"]["id"]
        body = {"branch_id": zb, "message": f"TEST launch {RUN}", "audience": "custom",
                "phones": ["9876500001", "+91 98765 00002", "123", "abc"]}
        assert requests.post(f"{API}/whatsapp/broadcast", headers=zb_billing["h"], json=body).status_code == 403
        r = requests.post(f"{API}/whatsapp/broadcast", headers=mgr, json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["recipients"] == 2 and d["invalid_skipped"] == 2 and d["mocked"] is True
        r = requests.post(f"{API}/whatsapp/broadcast", headers=admin, json={
            "branch_id": zb, "message": f"TEST cust {RUN}", "audience": "customers"})
        assert r.status_code == 200 and r.json()["recipients"] >= 1
        msgs = requests.get(f"{API}/whatsapp/messages", headers=admin,
                            params={"branch_id": zb, "kind": "broadcast"}).json()
        assert sum(1 for m in msgs if m.get("text") == f"TEST launch {RUN}") == 2


# ---------- Staff / auth ----------
class TestStaff:
    def test_create_validation(self, admin, masters):
        base = {"email": f"test_v_{RUN.lower()}@swarnaerp.in", "name": "TEST V", "role": "billing"}
        assert requests.post(f"{API}/auth/users", headers=admin, json={**base, "password": "Abc@1234"}).status_code == 400
        bid = masters["br"]["MG-BLR"]["id"]
        assert requests.post(f"{API}/auth/users", headers=admin, json={**base, "password": "Ab1", "branch_id": bid}).status_code == 400
        assert requests.post(f"{API}/auth/users", headers=admin, json={**base, "password": "Abcdefgh!", "branch_id": bid}).status_code == 400

    def test_manager_cannot_create(self, mgr, masters):
        r = requests.post(f"{API}/auth/users", headers=mgr, json={
            "email": f"test_m_{RUN.lower()}@x.in", "name": "x", "role": "billing", "password": "Abcd1234",
            "branch_id": masters["br"]["ZB-MAIN"]["id"]})
        assert r.status_code == 403

    def test_lifecycle_token_revocation(self, admin, masters):
        email = f"test_life_{RUN.lower()}@swarnaerp.in"
        r = requests.post(f"{API}/auth/users", headers=admin, json={
            "email": email, "name": "TEST Life", "role": "billing", "password": "Life@1234",
            "branch_id": masters["br"]["MG-BLR"]["id"]})
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        tok = login(email, "Life@1234")
        h = H(tok["access_token"])
        assert requests.get(f"{API}/auth/me", headers=h).status_code == 200
        # role change revokes
        r = requests.patch(f"{API}/auth/users/{uid}", headers=admin, json={"role": "manager"})
        assert r.status_code == 200 and r.json()["role"] == "manager"
        assert requests.get(f"{API}/auth/me", headers=h).status_code == 401
        assert requests.post(f"{API}/auth/refresh", json={"refresh_token": tok["refresh_token"]}).status_code == 401
        h = H(login(email, "Life@1234")["access_token"])
        # deactivate
        assert requests.patch(f"{API}/auth/users/{uid}", headers=admin, json={"active": False}).status_code == 200
        assert requests.get(f"{API}/auth/me", headers=h).status_code == 401
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "Life@1234"})
        assert r.status_code == 403
        requests.patch(f"{API}/auth/users/{uid}", headers=admin, json={"active": True})
        # reset password
        h = H(login(email, "Life@1234")["access_token"])
        assert requests.post(f"{API}/auth/users/{uid}/reset-password", headers=admin,
                             json={"password": "short"}).status_code == 400
        assert requests.post(f"{API}/auth/users/{uid}/reset-password", headers=admin,
                             json={"password": "NewPass@99"}).status_code == 200
        assert requests.get(f"{API}/auth/me", headers=h).status_code == 401
        login(email, "NewPass@99")

    def test_admin_self_protection(self, admin):
        me = requests.get(f"{API}/auth/me", headers=admin).json()
        assert requests.patch(f"{API}/auth/users/{me['id']}", headers=admin, json={"active": False}).status_code == 400
        assert requests.patch(f"{API}/auth/users/{me['id']}", headers=admin, json={"role": "manager"}).status_code == 400
        assert requests.get(f"{API}/auth/me", headers=admin).status_code == 200

    def test_brute_force(self):
        email = f"throwaway_{RUN.lower()}@nowhere.in"
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "bad"}).status_code
                 for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429, codes
