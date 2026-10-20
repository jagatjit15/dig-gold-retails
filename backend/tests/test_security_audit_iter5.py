# Iteration 5: security-audit fixes (SEC-001..004, CSRF hardening, scan scope, broadcast quota, headers)
import io
import os
import time
import uuid
import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ORIGIN = {"Origin": BASE_URL}
RUN = uuid.uuid4().hex[:6].upper()


def session(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code} {r.text}")
    s.headers.update(ORIGIN)
    return s


@pytest.fixture(scope="module")
def admin():
    return session("admin@swarnaerp.in", "Admin@12345")


@pytest.fixture(scope="module")
def mgr_blr():
    return session("manager.blr@swarnaerp.in", "Manager@123")


@pytest.fixture(scope="module")
def counter_blr():
    return session("counter.blr@swarnaerp.in", "Counter@123")


@pytest.fixture(scope="module")
def masters(admin):
    br = {b["code"]: b for b in admin.get(f"{API}/branches").json()}
    pur = {p["code"]: p for p in admin.get(f"{API}/purities").json()}
    cats = admin.get(f"{API}/categories").json()
    return {"br": br, "pur": pur, "cat": cats[0]}


def make_item(s, masters, branch):
    tag = f"TESTSEC-{RUN}-{uuid.uuid4().hex[:4].upper()}"
    r = s.post(f"{API}/items", json={
        "tag_id": tag, "category_id": masters["cat"]["id"], "purity_id": masters["pur"]["22K916"]["id"],
        "gross_wt": 5.0, "stone_wt": 0.0, "making_charge_type": "per_gram", "making_charge_value": 300,
        "branch_id": masters["br"][branch]["id"], "description": f"TEST sec item {tag}"})
    assert r.status_code == 200, r.text
    return r.json()


def png_bytes(fmt="PNG"):
    b = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 150, 30)).save(b, fmt)
    return b.getvalue()


PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"


# ---------- SEC-001: inline download XSS ----------
class TestFileDownloadXSS:
    @pytest.mark.parametrize("name,ctype,data", [
        ("TEST_xss.html", "text/html", b"<script>alert(document.cookie)</script>"),
        ("TEST_xss.svg", "image/svg+xml", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'),
        ("TEST_xss.xml", "application/xhtml+xml", b"<html xmlns='http://www.w3.org/1999/xhtml'><script>alert(1)</script></html>"),
        ("TEST_mixed.html", "TEXT/HTML; charset=utf-8", b"<b>x</b>"),
    ])
    def test_active_content_forced_attachment(self, admin, masters, name, ctype, data):
        r = admin.post(f"{API}/files", data={"owner_type": "branch", "owner_id": masters["br"]["MG-BLR"]["id"]},
                       files={"file": (name, data, ctype)})
        assert r.status_code == 200, r.text
        fid = r.json()["id"]
        try:
            d = admin.get(f"{API}/files/{fid}/download")
            assert d.status_code == 200
            assert d.headers["content-type"].startswith("application/octet-stream"), d.headers["content-type"]
            assert d.headers["content-disposition"].startswith("attachment"), d.headers["content-disposition"]
            assert d.headers.get("content-security-policy") == "default-src 'none'; sandbox"
            assert d.headers.get("x-content-type-options") == "nosniff"
            assert d.content == data
        finally:
            admin.delete(f"{API}/files/{fid}")

    @pytest.mark.parametrize("name,ctype,fmt", [
        ("TEST_p.png", "image/png", "PNG"), ("TEST_p.jpg", "image/jpeg", "JPEG"), ("TEST_d.pdf", "application/pdf", None),
    ])
    def test_safe_types_inline(self, admin, masters, name, ctype, fmt):
        data = png_bytes(fmt) if fmt else PDF
        r = admin.post(f"{API}/files", data={"owner_type": "branch", "owner_id": masters["br"]["MG-BLR"]["id"]},
                       files={"file": (name, data, ctype)})
        assert r.status_code == 200, r.text
        fid = r.json()["id"]
        try:
            d = admin.get(f"{API}/files/{fid}/download")
            assert d.status_code == 200
            assert d.headers["content-type"].startswith(ctype)
            assert d.headers["content-disposition"] == f'inline; filename="{name}"'
            assert d.content == data
        finally:
            admin.delete(f"{API}/files/{fid}")

    def test_filename_sanitized(self, admin, masters):
        r = admin.post(f"{API}/files", data={"owner_type": "branch", "owner_id": masters["br"]["MG-BLR"]["id"]},
                       files={"file": ('TEST_a"b\r\nX-Evil: 1.txt', b"hello", "text/plain")})
        assert r.status_code == 200, r.text
        fid = r.json()["id"]
        try:
            d = admin.get(f"{API}/files/{fid}/download")
            assert "x-evil" not in {k.lower() for k in d.headers}
            cd = d.headers["content-disposition"]
            assert cd.startswith('attachment; filename="TEST_a') and cd.count('"') == 2 and "\r" not in cd
        finally:
            admin.delete(f"{API}/files/{fid}")


# ---------- SEC-002: audit-log branch scope ----------
class TestAuditLogScope:
    def test_manager_sees_only_own_branch(self, mgr_blr, masters):
        # generate a null-branch login_failed entry
        requests.post(f"{API}/auth/login", json={"email": f"test_nouser_{RUN}@x.in", "password": "bad"})
        r = mgr_blr.get(f"{API}/audit-log", params={"limit": 500})
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) > 0
        blr = masters["br"]["MG-BLR"]["id"]
        bad = [x for x in rows if x.get("branch_id") != blr]
        assert not bad, f"{len(bad)} foreign rows, e.g. {bad[:2]}"

    def test_admin_sees_all(self, admin, masters):
        rows = admin.get(f"{API}/audit-log", params={"limit": 500}).json()
        ids = {x.get("branch_id") for x in rows}
        assert masters["br"]["ZB-MAIN"]["id"] in ids and masters["br"]["MG-BLR"]["id"] in ids
        assert None in ids  # login_failed etc.

    def test_counter_forbidden(self, counter_blr):
        assert counter_blr.get(f"{API}/audit-log").status_code == 403


# ---------- SEC-003: regex DoS / literal search ----------
class TestItemSearch:
    @pytest.mark.parametrize("q", ["(a+)+$", ".*", "[", "(?i)x", "\\", "a{1000000}", "^$|.*"])
    def test_metachars_literal_and_fast(self, admin, q):
        t = time.time()
        r = admin.get(f"{API}/items", params={"q": q})
        assert r.status_code == 200, r.text
        assert time.time() - t < 5
        for it in r.json():
            hay = " ".join(str(it.get(k) or "") for k in ("tag_id", "barcode", "rfid_epc", "huid")).lower()
            assert q.lower()[:64] in hay

    def test_partial_tag_search(self, admin, masters):
        it = make_item(admin, masters, "MG-BLR")
        r = admin.get(f"{API}/items", params={"q": it["tag_id"][:12].lower()})
        assert r.status_code == 200
        assert it["id"] in [x["id"] for x in r.json()]


# ---------- SEC-004: password reset / seed ----------
class TestPasswordReset:
    def test_reset_test_user(self, admin, masters):
        email = f"test_reset_{RUN.lower()}@swarnaerp.in"
        r = admin.post(f"{API}/auth/users", json={"email": email, "name": "TEST Reset", "password": "Orig@1234",
                                                  "role": "billing", "branch_id": masters["br"]["MG-BLR"]["id"]})
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        r = admin.post(f"{API}/auth/users/{uid}/reset-password", json={"password": "NewPw@5678"})
        assert r.status_code == 200, r.text
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": "NewPw@5678"}).status_code == 200
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": "Orig@1234"}).status_code == 401
        admin.patch(f"{API}/auth/users/{uid}", json={"active": False})

    def test_admin_login(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@swarnaerp.in", "password": "Admin@12345"})
        assert r.status_code == 200 and r.json()["user"]["role"] == "admin"


# ---------- CSRF Origin/Referer ----------
class TestCSRF:
    def _cookie_session(self):
        s = requests.Session()
        assert s.post(f"{API}/auth/login", json={"email": "admin@swarnaerp.in", "password": "Admin@12345"}).status_code == 200
        return s

    def test_no_origin_no_referer_blocked(self):
        s = self._cookie_session()
        for m, url, body in [("post", f"{API}/auth/logout", None),
                             ("patch", f"{API}/auth/users/nonexistent", {"name": "x"}),
                             ("delete", f"{API}/files/nonexistent", None)]:
            r = getattr(s, m)(url, json=body)
            assert r.status_code == 403, (m, r.status_code, r.text)
            assert r.json()["detail"] == "Origin not allowed"

    def test_refresh_cookie_only_blocked(self):
        s = self._cookie_session()
        assert s.post(f"{API}/auth/refresh").status_code == 403

    def test_origin_ok(self):
        s = self._cookie_session()
        r = s.post(f"{API}/auth/refresh", headers=ORIGIN)
        assert r.status_code == 200, r.text

    def test_referer_ok(self):
        s = self._cookie_session()
        r = s.post(f"{API}/auth/refresh", headers={"Referer": f"{BASE_URL}/billing"})
        assert r.status_code == 200, r.text

    @pytest.mark.parametrize("ref", ["https://evil.example/", f"{BASE_URL}.evil.example/x", f"{BASE_URL}@evil.example/"])
    def test_bad_referer_blocked(self, ref):
        s = self._cookie_session()
        assert s.post(f"{API}/auth/refresh", headers={"Referer": ref}).status_code == 403

    def test_login_without_origin_or_cookies(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@swarnaerp.in", "password": "Admin@12345"})
        assert r.status_code == 200


# ---------- POST /scan cross-branch disclosure ----------
class TestScanScope:
    def test_counter_blr_cannot_see_zb_item(self, admin, counter_blr, masters):
        it = make_item(admin, masters, "ZB-MAIN")
        r = counter_blr.post(f"{API}/scan", json={"code": it["tag_id"], "code_type": "barcode", "context": "lookup"})
        assert r.status_code == 200, r.text
        assert r.json()["found"] is False and r.json()["item_id"] is None
        # admin still finds it
        r = admin.post(f"{API}/scan", json={"code": it["tag_id"], "code_type": "barcode", "context": "lookup"})
        assert r.json()["found"] is True and r.json()["item_id"] == it["id"]

    def test_counter_blr_own_item_found(self, admin, counter_blr, masters):
        it = make_item(admin, masters, "MG-BLR")
        r = counter_blr.post(f"{API}/scan", json={"code": it["tag_id"], "code_type": "barcode", "context": "lookup"})
        assert r.json()["found"] is True and r.json()["item_id"] == it["id"]


# ---------- Broadcast quota (MG-BLR) ----------
class TestBroadcastQuota:
    def test_quota_429(self, mgr_blr, masters):
        bid = masters["br"]["MG-BLR"]["id"]
        statuses = []
        for i in range(12):
            r = mgr_blr.post(f"{API}/whatsapp/broadcast", json={
                "branch_id": bid, "message": f"TEST quota {RUN} {i}", "audience": "custom", "phones": ["9876500001"]})
            statuses.append(r.status_code)
            if r.status_code == 429:
                break
        assert statuses[-1] == 429, statuses
        assert set(statuses[:-1]) <= {200}, statuses
        # lookbook broadcast for same branch also blocked
        cards = mgr_blr.get(f"{API}/lookbook", params={"branch_id": bid}).json()
        if not cards:
            it = make_item(mgr_blr, masters, "MG-BLR")
            c = mgr_blr.post(f"{API}/lookbook", json={"branch_id": bid, "title": "TEST quota card", "item_ids": [it["id"]]})
            assert c.status_code == 200, c.text
            cards = [c.json()]
        r = mgr_blr.post(f"{API}/lookbook/{cards[0]['id']}/broadcast", json={"audience": "custom", "phones": ["9876500001"]})
        assert r.status_code == 429, r.text


# ---------- Security headers ----------
class TestHeaders:
    @pytest.mark.parametrize("path", ["/health", "/auth/me", "/items"])
    def test_headers(self, admin, path):
        r = admin.get(f"{API}{path}")
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"
        assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_headers_on_403(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": "admin@swarnaerp.in", "password": "Admin@12345"})
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 403
        print("403 headers:", {k: v for k, v in r.headers.items() if k.lower().startswith(("x-", "referrer"))})
