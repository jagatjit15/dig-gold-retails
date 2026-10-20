# SwarnaERP — Multi-branch Jewellery Retail ERP

SwarnaERP is a web ERP for Indian gold and jewellery retailers with one or more branches. It covers tagged inventory, scan-driven stock audits, GST billing with PDF invoices, old-gold exchange, branch transfers, file storage, label printing, staff accounts with branch-scoped access, WhatsApp invoice and broadcast hooks, and WhatsApp-ready launch lookbook cards.

> For internals (data model, flows, security, every endpoint) see **[ARCHITECTURE.md](./ARCHITECTURE.md)**.

---

## Features

| Module | What it does |
|---|---|
| **Dashboard** | Daily metal rate board, in-stock count, net weight and approximate valuation for the selected branch |
| **Masters & Rates** | Branches (GSTIN, state code), purities (fineness), categories (HSN, GST %), daily rates per purity |
| **Inventory** | Tagged items with tag ID, barcode, RFID EPC, HUID, gross/stone/net weight (3 decimals), making charge (per gram / % / fixed); photos and documents per item |
| **Scan Lookup** | USB keyboard-wedge barcode/RFID readers plus camera scanning (phone, laptop or external camera); duplicate-scan debounce |
| **Stock Audit** | Scan sessions per branch with live variance: found, missing, unknown, wrong branch, wrong status |
| **Billing** | Scan-to-bill counter, per-line making override, CGST+SGST or IGST (by customer state), round off, payment mode, old-gold exchange, GST PDF invoice; sold items leave stock atomically |
| **Old Gold Exchange** | Net weight × tested fineness × today's fine rate − deduction %, deducted after GST; booked as old-gold stock lots |
| **Transfers** | Draft → scan-out → dispatch (in transit) → scan-in → receive; missing and unexpected items flagged; late scan-in supported |
| **Label Print** | TSPL (TSC) / ZPL (Zebra) tag payload generator with live preview |
| **Documents** | Per-branch document library (any file type, up to 25 MB) |
| **WhatsApp** | Pluggable provider slot; invoices sent automatically when a bill has a phone number; broadcasts; outbox (**mock provider by default**) |
| **Lookbook** | 1080×1350 PNG new-collection card from item photos with weight and price incl. GST; broadcast on WhatsApp |
| **Staff** | Admin-managed accounts with roles and branches; deactivate and password reset revoke sessions immediately |
| **Audit Log** | Append-only, SHA-256 hash-chained log of logins and every change |

Roles: `admin` (all branches), `manager`, `billing`, `auditor` (scoped to one branch).

---

## Tech stack

- **Frontend:** React 19 (CRA + CRACO), React Router, Tailwind CSS, shadcn/ui (Radix), lucide-react, sonner, axios, html5-qrcode
- **Backend:** Python 3.11, FastAPI, Motor (async MongoDB), Pydantic v2, PyJWT, bcrypt, ReportLab (PDF), Pillow (lookbook cards), requests
- **Database:** MongoDB
- **File storage:** Emergent managed object storage (S3-like API through the integrations proxy)
- **Fonts:** Inter (UI), Cormorant Garamond (brand, invoice), JetBrains Mono (codes), Noto Sans Devanagari/Oriya; Cormorant and Noto Sans TTFs are bundled in `backend/fonts` for PDF and PNG rendering

---

## Repository layout

```
backend/
  server.py              FastAPI app, /api router, CORS, Origin check, startup (indexes, seed, storage init)
  db.py                  Motor client from MONGO_URL / DB_NAME
  models.py              Shared Pydantic models (users, masters, items, movements, scans, audit)
  auth.py                bcrypt, JWT, cookie helpers, get_current_user, require_roles, branch scoping
  audit.py               Hash-chained audit log writer
  seed.py                Idempotent seed (admin from env, sample branches/purities/categories/rates)
  storage.py             Object storage client (init, put, get)
  invoice_pdf.py         GST tax invoice PDF builder (ReportLab)
  whatsapp.py            WhatsApp provider interface, MockProvider, invoice sender, outbox
  lookbook.py            Lookbook PNG composer (Pillow)
  fonts/                 TTFs used by PDF/PNG rendering
  routers/
    auth_router.py       login / refresh / logout / me / staff CRUD
    masters_router.py    branches, purities, categories, daily rates
    inventory_router.py  items, scan, movements, stock summary, audit sessions, audit log
    billing_router.py    quote, bill, list, PDF, old-gold lots
    files_router.py      upload / list / download / soft delete
    transfers_router.py  branch transfer lifecycle
    whatsapp_router.py   status, invoice send, broadcast, outbox
    lookbook_router.py   card create, list, photo items, broadcast
  tests/                 pytest suites (run against a live backend URL)
frontend/
  src/App.js             Routes + auth guard
  src/context/AuthContext.jsx  session, branch selection
  src/lib/api.js         axios instance (cookies, refresh-on-401, errMsg)
  src/components/        Layout, CameraScanner, FileManager, OldGoldCard, ui/ (shadcn)
  src/pages/             one file per screen
memory/                  PRD and test credentials (dev only)
```

---

## Getting started (local)

### Prerequisites
Node 18+ with **yarn** (don't use npm), Python 3.11, and MongoDB 6+ running locally.

### 1. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the values
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Frontend
```bash
cd frontend
yarn install
cp .env.example .env        # REACT_APP_BACKEND_URL=http://localhost:8001
yarn start                  # http://localhost:3000
```

Locally the frontend (3000) and backend (8001) run on different ports. Auth cookies are `Secure`, so use HTTPS locally (for example a local reverse proxy that serves both under one origin with `/api` → 8001), or test against the hosted preview. In hosted environments, an ingress routes `/api/*` to the backend and everything else to the frontend on the same origin.

### Environment variables

**backend/.env**

| Key | Purpose |
|---|---|
| `MONGO_URL` | MongoDB connection string |
| `DB_NAME` | Database name |
| `JWT_SECRET` | Long random string used to sign JWTs (`python -c "import secrets;print(secrets.token_urlsafe(48))"`) |
| `CORS_ORIGINS` | Comma-separated allowed origins. **Must include every domain the app is served from**; it is also used by the Origin (CSRF) check |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Seeded admin account, created on first start only. Later password changes are made in the app (Staff → reset password); use a strong, unique value in production |
| `EMERGENT_LLM_KEY` | Key for Emergent object storage (file uploads, lookbook cards) |
| `WHATSAPP_PROVIDER` | Provider key registered in `whatsapp.py` (`mock` by default) |

**frontend/.env**

| Key | Purpose |
|---|---|
| `REACT_APP_BACKEND_URL` | Base URL of the backend; the app calls `${REACT_APP_BACKEND_URL}/api/...` |

`.env` files are never committed. Use the `.env.example` templates.

### Default login (development)
`admin@swarnaerp.in` with the `ADMIN_PASSWORD` you set. Create other staff from **Staff** in the UI.

---

## Running tests

The backend tests are integration tests that call a running backend:
```bash
cd backend
REACT_APP_BACKEND_URL=https://your-host pytest -q tests/
```
They use cookie sessions (`requests.Session`). Five wrong logins for the same email lock it for 15 minutes; clear with `db.login_attempts.deleteMany({})`.

---

## Connecting a real WhatsApp provider

1. In `backend/whatsapp.py`, subclass `WhatsAppProvider` and implement `send_text(to, text)` and `send_document(to, filename, data, mime, caption)`. Optionally override `send_image`. Return `{"status": "sent", "provider_message_id": "..."}`.
2. Read your provider credentials from env inside the class (never hardcode them).
3. Register it in `PROVIDERS = {"mock": MockProvider, "yourkey": YourProvider}`.
4. Set `WHATSAPP_PROVIDER=yourkey` in `backend/.env` and restart. The WhatsApp page banner disappears when `mocked` is false.

Phone numbers are normalised to digits, and 10-digit numbers get a `91` prefix.

---

## Contributing

- Every backend route lives under `/api` (included through `api_router` in `server.py`).
- Every endpoint must use `get_current_user` or `require_roles(...)`, and must call `enforce_branch(user, branch_id)` for branch-owned data.
- Never return raw Mongo documents. Query with `{"_id": 0}` and return Pydantic models.
- Use `datetime.now(timezone.utc)` (`models.now_iso()`); IDs are UUID strings (`models.new_id()`).
- Stock changes must write a `StockMovement` (append-only ledger) and, for user actions, `log_event(...)`.
- Change item status with a **conditional update** (`{"id": x, "status": "in_stock"}`) to avoid double-selling.
- Frontend: named exports for components and default exports for pages; shadcn components from `src/components/ui`; give every interactive element a `data-testid`; show errors with `toast.error(errMsg(err))`.
- Colours come from CSS variables in `src/index.css` (`--brand`, `--gold`, `--panel`, `--line`, `--success`, `--warning`, `--danger`, `--info`). Don't reuse shadcn variable names for custom colours.
- Dependencies: `yarn add` (frontend) and `pip install … && pip freeze > requirements.txt` (backend).

## Known limitations / roadmap
- WhatsApp is mocked until a provider is plugged in.
- No write-off flow yet for transfer items that never arrive.
- No customer master (KYC/PAN), estimates, split payments, purchases, karigar or schemes yet.
- Logout clears cookies but doesn't revoke a copied refresh token server-side.
- Web fonts load from Google Fonts (not bundled for offline use).
