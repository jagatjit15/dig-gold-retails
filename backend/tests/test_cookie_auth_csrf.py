# Iteration 4: httpOnly cookie session auth, refresh/logout, CSRF origin middleware, admin seed, revocation, branch scope
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ORIGIN = {"Origin": BASE_URL}
ADMIN = ("admin@swarnaerp.in", "Admin@12345")
BLR = ("counter.blr@swarnaerp.in", "Counter@123")


def session_login(email, pw):
    s = requests.Session()
    s.headers.update(ORIGIN)
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    return s, r


@pytest.fixture(scope="module")
def admin():
    s, r = session_login(*ADMIN)
    assert r.status_code == 200, r.text
    return s


# --- Login sets cookies, body only has user
class TestCookieLogin:
    def test_login_sets_cookies_and_body_only_user(self):
        s, r = session_login(*ADMIN)
        assert r.status_code == 200, r.text
        body = r.json()
        assert list(body.keys()) == ["user"]
        assert body["user"]["email"] == ADMIN[0]
        assert body["user"]["role"] == "admin"
        assert "password_hash" not in body["user"]
        assert "access_token" not in body and "refresh_token" not in body
        names = {c.name: c for c in s.cookies}
        assert "swarna_access" in names and "swarna_refresh" in names
        assert names["swarna_access"].path == "/api"
        assert names["swarna_refresh"].path == "/api/auth"
        assert names["swarna_access"].secure and names["swarna_refresh"].secure
        sc = r.headers.get("set-cookie", "").lower()
        assert "httponly" in sc
        print("Set-Cookie:", r.headers.get("set-cookie"))

    def test_me_with_and_without_cookie(self, admin):
        r = admin.get(f"{API}/auth/me")
        assert r.status_code == 200 and r.json()["email"] == ADMIN[0]
        assert requests.get(f"{API}/auth/me").status_code == 401

    def test_refresh_issues_new_cookies(self):
        s, _ = session_login(*ADMIN)
        old_access = s.cookies.get("swarna_access", path="/api")
        s.cookies.clear(domain=None) if False else None
        # drop access only, keep refresh
        for c in list(s.cookies):
            if c.name == "swarna_access":
                s.cookies.clear(c.domain, c.path, c.name)
        assert s.get(f"{API}/auth/me").status_code == 401
        r = s.post(f"{API}/auth/refresh")
        assert r.status_code == 200, r.text
        assert list(r.json().keys()) == ["user"]
        assert "swarna_access" in r.cookies and "swarna_refresh" in r.cookies
        assert s.get(f"{API}/auth/me").status_code == 200
        assert old_access  # was present initially

    def test_refresh_without_cookie_401(self):
        r = requests.post(f"{API}/auth/refresh", headers=ORIGIN)
        assert r.status_code == 401

    def test_logout_clears_session(self):
        s, _ = session_login(*ADMIN)
        assert s.get(f"{API}/auth/me").status_code == 200
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200 and r.json() == {"ok": True}
        assert s.get(f"{API}/auth/me").status_code == 401
        assert s.post(f"{API}/auth/refresh").status_code == 401


# --- CSRF origin middleware
class TestOrigin:
    def test_evil_origin_post_blocked(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]},
                          headers={"Origin": "https://evil.example"})
        assert r.status_code == 403
        assert r.json()["detail"] == "Origin not allowed"
        assert "swarna_access" not in r.cookies

    def test_evil_origin_authenticated_write_blocked(self, admin):
        r = admin.post(f"{API}/auth/logout", headers={"Origin": "https://evil.example"})
        assert r.status_code == 403
        r = admin.patch(f"{API}/auth/users/x", json={"name": "y"}, headers={"Origin": "https://evil.example"})
        assert r.status_code == 403

    def test_app_origin_ok(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]}, headers=ORIGIN)
        assert r.status_code == 200

    def test_get_not_blocked(self, admin):
        r = admin.get(f"{API}/auth/me", headers={"Origin": "https://evil.example"})
        assert r.status_code == 200

    def test_cors_preflight_allowed_origin(self):
        r = requests.options(f"{API}/auth/login", headers={
            "Origin": BASE_URL, "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") == BASE_URL
        assert r.headers.get("access-control-allow-credentials") == "true"

    def test_cors_preflight_evil_origin(self):
        r = requests.options(f"{API}/auth/login", headers={
            "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") != "https://evil.example"


# --- Brute force, revocation, branch scoping with cookie sessions
class TestSecurity:
    def test_brute_force_429(self):
        email = f"TEST_bf_{uuid.uuid4().hex[:6]}@nowhere.in"
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "wrong1234"},
                               headers=ORIGIN).status_code for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429, codes

    def test_role_change_and_deactivate_revoke_cookie_session(self, admin):
        br = {b["code"]: b for b in admin.get(f"{API}/branches").json()}
        email = f"test_ck_{uuid.uuid4().hex[:6]}@swarnaerp.in"
        r = admin.post(f"{API}/auth/users", json={"email": email, "name": "TEST Cookie", "role": "billing",
                                                  "password": "Cookie@123", "branch_id": br["MG-BLR"]["id"]})
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        s, lr = session_login(email, "Cookie@123")
        assert lr.status_code == 200
        assert s.get(f"{API}/auth/me").status_code == 200
        assert admin.patch(f"{API}/auth/users/{uid}", json={"role": "manager"}).status_code == 200
        assert s.get(f"{API}/auth/me").status_code == 401
        assert s.post(f"{API}/auth/refresh").status_code == 401
        s2, _ = session_login(email, "Cookie@123")
        assert s2.get(f"{API}/auth/me").json()["role"] == "manager"
        assert admin.patch(f"{API}/auth/users/{uid}", json={"active": False}).status_code == 200
        assert s2.get(f"{API}/auth/me").status_code == 401
        _, lr3 = session_login(email, "Cookie@123")
        assert lr3.status_code == 403

    def test_branch_scope_counter_blr(self):
        s, r = session_login(*BLR)
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "billing"
        brs = s.get(f"{API}/branches").json()
        codes = {b["code"] for b in brs}
        assert codes == {"MG-BLR"}, codes
        admin_s, _ = session_login(*ADMIN)
        zb = [b for b in admin_s.get(f"{API}/branches").json() if b["code"] == "ZB-MAIN"][0]
        r = s.get(f"{API}/items", params={"branch_id": zb["id"]})
        assert r.status_code in (403, 200)
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("items", [])
            assert all(i.get("branch_id") != zb["id"] for i in items)
