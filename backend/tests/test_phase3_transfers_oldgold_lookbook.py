# Phase 3 regression: branch transfers, old gold exchange on bills, launch lookbook cards
import io
import math
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("admin@swarnaerp.in", "Admin@12345")
BLR = ("counter.blr@swarnaerp.in", "Counter@123")
MGR = ("manager.zb@swarnaerp.in", "Manager@123")
MGR_BLR = ("manager.blr@swarnaerp.in", "Manager@123")
RUN = uuid.uuid4().hex[:6].upper()


def login(email, pw):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw})


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def tok(email, pw):
    r = login(email, pw)
    assert r.status_code == 200, r.text
    return H(r.json()["access_token"])


@pytest.fixture(scope="session")
def admin():
    return tok(*ADMIN)


@pytest.fixture(scope="session")
def blr():
    return tok(*BLR)


@pytest.fixture(scope="session")
def mgr():
    return tok(*MGR)


@pytest.fixture(scope="session")
def masters(admin):
    br = {b["code"]: b for b in requests.get(f"{API}/branches", headers=admin).json()}
    pur = {p["code"]: p for p in requests.get(f"{API}/purities", headers=admin).json()}
    cats = requests.get(f"{API}/categories", headers=admin).json()
    rates = {r["purity_code"]: r["rate_per_gram"]
             for r in requests.get(f"{API}/daily-rates/latest", headers=admin).json()}
    return {"br": br, "pur": pur, "cat": cats[0], "rates": rates}


@pytest.fixture(scope="session")
def mgr_blr(admin, masters):
    r = login(*MGR_BLR)
    if r.status_code != 200:
        c = requests.post(f"{API}/auth/users", headers=admin, json={
            "email": MGR_BLR[0], "name": "BLR Manager", "password": MGR_BLR[1],
            "role": "manager", "branch_id": masters["br"]["MG-BLR"]["id"]})
        assert c.status_code in (200, 201), c.text
        r = login(*MGR_BLR)
    assert r.status_code == 200, r.text
    return H(r.json()["access_token"])


def make_item(admin, masters, branch="ZB-MAIN", gross=10.0, stone=1.0, desc=None):
    tag = f"TEST-{RUN}-{uuid.uuid4().hex[:5].upper()}"
    r = requests.post(f"{API}/items", headers=admin, json={
        "tag_id": tag, "category_id": masters["cat"]["id"], "purity_id": masters["pur"]["22K916"]["id"],
        "gross_wt": gross, "stone_wt": stone, "making_charge_type": "per_gram", "making_charge_value": 500,
        "branch_id": masters["br"][branch]["id"], "description": desc or f"TEST necklace {tag}"})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------- Transfers ----------------
class TestTransfers:
    def test_branches_for_any_user(self, blr):
        r = requests.get(f"{API}/transfers/branches", headers=blr)
        assert r.status_code == 200
        codes = {b["code"] for b in r.json()}
        assert {"ZB-MAIN", "MG-BLR"} <= codes

    def test_create_validation(self, admin, blr, masters):
        zb, mg = masters["br"]["ZB-MAIN"]["id"], masters["br"]["MG-BLR"]["id"]
        r = requests.post(f"{API}/transfers", headers=admin, json={"from_branch_id": zb, "to_branch_id": zb})
        assert r.status_code == 400
        r = requests.post(f"{API}/transfers", headers=blr, json={"from_branch_id": mg, "to_branch_id": zb})
        assert r.status_code == 403

    def test_full_flow(self, admin, mgr, mgr_blr, blr, masters):
        zb, mg = masters["br"]["ZB-MAIN"]["id"], masters["br"]["MG-BLR"]["id"]
        a, b = make_item(admin, masters), make_item(admin, masters)
        other_branch = make_item(admin, masters, branch="MG-BLR")
        r = requests.post(f"{API}/transfers", headers=mgr, json={"from_branch_id": zb, "to_branch_id": mg})
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["status"] == "draft" and t["transfer_no"].startswith("TR-ZB-MAIN-")
        tid = t["id"]
        # empty dispatch -> 400
        assert requests.post(f"{API}/transfers/{tid}/dispatch", headers=mgr).status_code == 400
        # scan out
        for it in (a, b):
            r = requests.post(f"{API}/transfers/{tid}/scan-out", headers=mgr, json={"code": it["tag_id"]})
            assert r.status_code == 200, r.text
        assert len(r.json()["items"]) == 2
        # duplicate -> 409, other branch -> 400, unknown -> 404
        assert requests.post(f"{API}/transfers/{tid}/scan-out", headers=mgr, json={"code": a["tag_id"]}).status_code == 409
        assert requests.post(f"{API}/transfers/{tid}/scan-out", headers=mgr, json={"code": other_branch["tag_id"]}).status_code == 400
        assert requests.post(f"{API}/transfers/{tid}/scan-out", headers=mgr, json={"code": "NOPE-" + RUN}).status_code == 404
        # already on another draft -> 409
        t2 = requests.post(f"{API}/transfers", headers=mgr, json={"from_branch_id": zb, "to_branch_id": mg}).json()
        r = requests.post(f"{API}/transfers/{t2['id']}/scan-out", headers=mgr, json={"code": a["tag_id"]})
        assert r.status_code == 409 and t["transfer_no"][:3] == "TR-"
        # remove + re-add
        r = requests.delete(f"{API}/transfers/{tid}/items/{b['id']}", headers=mgr)
        assert r.status_code == 200 and len(r.json()["items"]) == 1
        requests.post(f"{API}/transfers/{tid}/scan-out", headers=mgr, json={"code": b["tag_id"]})
        # cancel draft t2 OK
        r = requests.post(f"{API}/transfers/{t2['id']}/cancel", headers=mgr)
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
        # dispatch
        r = requests.post(f"{API}/transfers/{tid}/dispatch", headers=mgr)
        assert r.status_code == 200 and r.json()["status"] == "in_transit"
        assert requests.get(f"{API}/items/{a['id']}", headers=admin).json()["status"] == "in_transit"
        # cancel non-draft -> 400
        assert requests.post(f"{API}/transfers/{tid}/cancel", headers=mgr).status_code == 400
        # billing on in-transit item blocked
        r = requests.post(f"{API}/bills/quote", headers=admin, json={"branch_id": zb, "item_ids": [a["id"]]})
        assert r.status_code in (400, 409)
        lk = requests.get(f"{API}/scan/lookup", headers=admin, params={"code": a["tag_id"]})
        print("scan lookup in-transit:", lk.status_code, lk.text[:300])
        # scan-in by source manager -> 403
        assert requests.post(f"{API}/transfers/{tid}/scan-in", headers=mgr, json={"code": a["tag_id"]}).status_code == 403
        # billing role at dest -> 403
        assert requests.post(f"{API}/transfers/{tid}/scan-in", headers=blr, json={"code": a["tag_id"]}).status_code == 403
        # unknown code -> 404 + recorded
        bad = f"UNK-{RUN}"
        assert requests.post(f"{API}/transfers/{tid}/scan-in", headers=mgr_blr, json={"code": bad}).status_code == 404
        r = requests.post(f"{API}/transfers/{tid}/scan-in", headers=mgr_blr, json={"code": a["tag_id"]})
        assert r.status_code == 200
        t = r.json()
        assert bad in t["unexpected_codes"]
        assert [i["received"] for i in t["items"] if i["item_id"] == a["id"]] == [True]
        # incoming list at dest
        lst = requests.get(f"{API}/transfers", headers=mgr_blr, params={"branch_id": mg}).json()
        assert any(x["id"] == tid for x in lst)
        lst = requests.get(f"{API}/transfers", headers=mgr, params={"branch_id": zb}).json()
        assert any(x["id"] == tid for x in lst)
        # receive
        r = requests.post(f"{API}/transfers/{tid}/receive", headers=mgr_blr)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["status"] == "received_with_variance"
        assert t["missing_item_ids"] == [b["id"]]
        ia = requests.get(f"{API}/items/{a['id']}", headers=admin).json()
        ib = requests.get(f"{API}/items/{b['id']}", headers=admin).json()
        assert ia["status"] == "in_stock" and ia["branch_id"] == mg
        assert ib["status"] == "in_transit" and ib["branch_id"] == zb
        # receive again -> 400
        assert requests.post(f"{API}/transfers/{tid}/receive", headers=mgr_blr).status_code == 400
        # movements
        mv = requests.get(f"{API}/movements", headers=admin, params={"branch_id": mg}).json()
        assert any(m["movement_type"] == "transfer_in" and m["item_id"] == a["id"] for m in mv)
        mv = requests.get(f"{API}/movements", headers=admin, params={"branch_id": zb}).json()
        assert sum(1 for m in mv if m["movement_type"] == "transfer_out" and m.get("reference") == t["transfer_no"]) == 2


# ---------------- Old gold ----------------
def per_fine(masters, metal="gold"):
    ps = sorted([p for p in masters["pur"].values() if p["metal"] == metal], key=lambda p: -p["fineness"])
    for p in ps:
        if p["code"] in masters["rates"]:
            return masters["rates"][p["code"]] / p["fineness"]


class TestOldGold:
    def test_quote_and_bill(self, admin, masters):
        zb = masters["br"]["ZB-MAIN"]["id"]
        it = make_item(admin, masters, gross=20, stone=0)
        og = [{"description": "TEST old chain", "metal": "gold", "fineness": 0.916,
               "gross_wt": 5.0, "stone_wt": 0.5, "deduction_pct": 2}]
        r = requests.post(f"{API}/bills/quote", headers=admin, json={"branch_id": zb, "item_ids": [it["id"]], "old_gold": og})
        assert r.status_code == 200, r.text
        q = r.json()
        ln = q["old_gold"][0]
        pf = per_fine(masters)
        assert ln["net_wt"] == 4.5 and abs(ln["fine_wt"] - 4.122) < 1e-6
        assert abs(ln["value"] - round(4.122 * pf * 0.98, 2)) < 0.02
        assert q["old_gold_total"] == math.floor(ln["value"] + 0.5)
        assert q["net_payable"] == q["grand_total"] - q["old_gold_total"]
        r = requests.post(f"{API}/bills", headers=admin, json={
            "branch_id": zb, "item_ids": [it["id"]], "old_gold": og, "customer_name": "TEST OG"})
        assert r.status_code == 200, r.text
        bill = r.json()
        assert bill["net_payable"] == q["net_payable"]
        lots = requests.get(f"{API}/bills/old-gold", headers=admin, params={"branch_id": zb}).json()
        assert any(l["bill_id"] == bill["id"] and l["net_wt"] == 4.5 for l in lots)
        assert all("_id" not in l for l in lots)
        pdf = requests.get(f"{API}/bills/{bill['id']}/pdf", headers=admin)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
        mv = requests.get(f"{API}/movements", headers=admin, params={"branch_id": zb}).json()
        assert any(m["movement_type"] == "receipt" and m.get("reference") == f"OLDGOLD:{bill['bill_no']}" for m in mv)

    def test_pdf_text(self, admin, masters):
        zb = masters["br"]["ZB-MAIN"]["id"]
        bills = requests.get(f"{API}/bills", headers=admin, params={"branch_id": zb}).json()
        b = next(x for x in bills if x.get("old_gold"))
        pdf = requests.get(f"{API}/bills/{b['id']}/pdf", headers=admin).content
        try:
            from pypdf import PdfReader
        except ImportError:
            pytest.skip("pypdf missing")
        text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        assert "Net payable" in text and "old gold" in text.lower()

    def test_validation(self, admin, masters):
        zb = masters["br"]["ZB-MAIN"]["id"]
        it = make_item(admin, masters, gross=2, stone=0)
        base = {"branch_id": zb, "item_ids": [it["id"]]}
        og = {"metal": "gold", "fineness": 1.2, "gross_wt": 1}
        assert requests.post(f"{API}/bills/quote", headers=admin, json={**base, "old_gold": [og]}).status_code == 422
        og = {"metal": "gold", "fineness": 0, "gross_wt": 1}
        assert requests.post(f"{API}/bills/quote", headers=admin, json={**base, "old_gold": [og]}).status_code == 422
        og = {"metal": "gold", "fineness": 0.9, "gross_wt": 1, "stone_wt": 1}
        assert requests.post(f"{API}/bills/quote", headers=admin, json={**base, "old_gold": [og]}).status_code == 400
        og = {"metal": "gold", "fineness": 0.999, "gross_wt": 100}
        r = requests.post(f"{API}/bills/quote", headers=admin, json={**base, "old_gold": [og]})
        assert r.status_code == 400
        r = requests.post(f"{API}/bills", headers=admin, json={**base, "old_gold": [og], "customer_name": "TEST"})
        assert r.status_code == 400
        assert requests.get(f"{API}/items/{it['id']}", headers=admin).json()["status"] == "in_stock"


# ---------------- Lookbook ----------------
class TestLookbook:
    def test_create_download_broadcast(self, admin, mgr, blr, masters):
        zb, mg = masters["br"]["ZB-MAIN"]["id"], masters["br"]["MG-BLR"]["id"]
        items = [make_item(admin, masters, gross=12.345, stone=0.5) for _ in range(3)]
        ids = [i["id"] for i in items]
        # billing -> 403
        r = requests.post(f"{API}/lookbook", headers=blr, json={"branch_id": mg, "title": "X", "item_ids": ids})
        assert r.status_code == 403
        # 7 items -> 422
        r = requests.post(f"{API}/lookbook", headers=mgr, json={"branch_id": zb, "title": "X", "item_ids": ids * 3})
        assert r.status_code == 422
        # other branch item -> 400
        o = make_item(admin, masters, branch="MG-BLR")
        r = requests.post(f"{API}/lookbook", headers=admin, json={"branch_id": zb, "title": "X", "item_ids": [ids[0], o["id"]]})
        assert r.status_code == 400
        r = requests.post(f"{API}/lookbook", headers=mgr, json={"branch_id": zb, "title": f"TEST Card {RUN}",
                                                                 "subtitle": "Diwali", "item_ids": ids})
        assert r.status_code == 200, r.text
        card = r.json()
        assert card["file_id"] and card["item_ids"] == ids
        d = requests.get(f"{API}/files/{card['file_id']}/download", headers=mgr)
        assert d.status_code == 200 and d.content[:8] == b"\x89PNG\r\n\x1a\n"
        from PIL import Image
        assert Image.open(io.BytesIO(d.content)).size == (1080, 1350)
        lst = requests.get(f"{API}/lookbook", headers=mgr, params={"branch_id": zb}).json()
        assert any(c["id"] == card["id"] for c in lst)
        r = requests.post(f"{API}/lookbook/{card['id']}/broadcast", headers=mgr, json={
            "message": f"TEST launch {RUN}", "audience": "custom", "phones": ["9876543210", "123", "+91 9123456789"]})
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["recipients"] == 2 and res["invalid_skipped"] == 1 and res["mocked"] is True
        msgs = requests.get(f"{API}/whatsapp/messages", headers=mgr, params={"branch_id": zb}).json()
        mine = [m for m in msgs if m.get("lookbook_id") == card["id"]]
        assert len(mine) == 2 and all(m["kind"] == "lookbook" and m["status"] == "mocked" for m in mine)
        # billing cannot broadcast
        assert requests.post(f"{API}/lookbook/{card['id']}/broadcast", headers=blr,
                             json={"audience": "custom", "phones": ["9876543210"]}).status_code == 403

    def test_sold_item_rejected(self, admin, masters):
        """Spec: pick in-stock items only"""
        zb = masters["br"]["ZB-MAIN"]["id"]
        it = make_item(admin, masters)
        requests.post(f"{API}/bills", headers=admin, json={"branch_id": zb, "item_ids": [it["id"]], "customer_name": "TEST"})
        r = requests.post(f"{API}/lookbook", headers=admin, json={"branch_id": zb, "title": "TEST sold", "item_ids": [it["id"]]})
        assert r.status_code == 400, f"sold item accepted on lookbook: {r.status_code}"
