# Auth testing notes (SwarnaERP)
- Session = httpOnly cookies: `swarna_access` (15 min, path /api) and `swarna_refresh` (7 days, path /api/auth). Tokens are NOT in response bodies or localStorage.
- POST /api/auth/login -> {user} + cookies; POST /api/auth/refresh uses refresh cookie; POST /api/auth/logout clears cookies; GET /api/auth/me.
- Bearer header still accepted as fallback but no endpoint returns tokens anymore; use a cookie session (requests.Session) in tests.
- Origin check: POST/PUT/PATCH/DELETE with an Origin not in CORS_ORIGINS -> 403.
- Admin seeded from ADMIN_EMAIL / ADMIN_PASSWORD in backend/.env (password re-synced on startup).
- Brute force: 5 failed logins per IP+email -> 429 for 15 min. Role/branch/active change or password reset -> old sessions 401.
- Credentials: /app/memory/test_credentials.md
