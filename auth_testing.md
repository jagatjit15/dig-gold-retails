# Auth testing notes (SwarnaERP)
- Bearer-token JWT (access 15 min, refresh 7 days) stored in localStorage; tokens carry `tv` (token_version).
- bcrypt hashes in `users.password_hash` (start with `$2b$`). Unique index on users.email.
- Brute force: 5 failed logins per IP+email -> 429 for 15 min (`login_attempts` collection).
- PATCH /api/auth/users/{id} changing role/branch/active, or POST /reset-password, increments token_version -> old tokens get 401.
- Non-admin users: GET /api/branches returns only their branch; other-branch item/bill/file access -> 403.
- Credentials: /app/memory/test_credentials.md
