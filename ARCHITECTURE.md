# SwarnaERP — Architecture Guide

This document is for full-stack developers who will maintain and extend SwarnaERP. It covers the system layout, every module, the data model, the main data flows, security and how to extend the code safely.

---

## 1. System overview

```
 Browser (React SPA)                         Ingress (same origin)                 Backend (FastAPI :8001)
 ┌─────────────────────────┐   /api/*  ┌───────────────────────┐   ┌──────────────────────────────────────┐
 │ Pages / Components      │──────────▶│ path routing          │──▶│ api_router (/api)                     │
 │ AuthContext (session,   │  cookies  │  /api → :8001         │   │  ├ auth  ├ masters ├ inventory/scan   │
 │   branch selection)     │◀──────────│  /*   → :3000         │   │  ├ billing ├ files ├ transfers        │
 │ axios api.js            │           └───────────────────────┘   │  ├ whatsapp ├ lookbook                │
 │ html5-qrcode (camera)   │                                       │ middleware: Origin check, CORS        │
 │ USB wedge → <input>     │                                       │ startup: indexes, seed, storage init  │
 └─────────────────────────┘                                       └──────┬───────────────┬────────────────┘
                                                                          │ Motor         │ HTTPS
                                                                  ┌───────▼──────┐  ┌─────▼────────────────┐
                                                                  │   MongoDB    │  │ Emergent Object      │
                                                                  │ (DB_NAME)    │  │ Storage (files, PNG) │
                                                                  └──────────────┘  └──────────────────────┘
                                                                          │
                                                          WhatsApp provider slot (whatsapp.py, mock by default)
```

- **Single origin:** the SPA and API share one host, and the ingress sends `/api/*` to the backend. That's why auth can use httpOnly cookies.
- **Stateless backend:** sessions are JWT cookies. All state lives in MongoDB and object storage, so backend instances can scale horizontally (except the in-process storage key cache, which re-initialises itself).
- **Rendering on the server:** PDF invoices (ReportLab) and lookbook PNGs (Pillow) are built in the backend, so output doesn't depend on the client device.

---

## 2. Tech stack

| Layer | Technology | Notes |
|---|---|---|
| UI | React 19, React Router 7, Tailwind, shadcn/ui (Radix) | CRA + CRACO; `@/` alias → `src/` |
| HTTP | axios (`withCredentials: true`) | one instance in `src/lib/api.js` |
| Scanning | USB keyboard wedge (text input + Enter), `html5-qrcode` | QR, Code128/39/93, EAN-8/13, UPC-A/E, ITF, DataMatrix |
| API | FastAPI, Pydantic v2 | all routes under `/api` |
| DB driver | Motor (async) | `db.py` |
| Auth | PyJWT HS256, bcrypt | cookies, token versioning |
| PDF | ReportLab | `invoice_pdf.py` |
| Images | Pillow | `lookbook.py` |
| Files | Emergent Object Storage | `storage.py` (sync `requests`, called via `asyncio.to_thread`) |

---

## 3. Backend modules

### 3.1 `server.py`
- Builds `app` and `api_router = APIRouter(prefix="/api")`, includes every router, and exposes `/api/` and `/api/health`.
- **`check_origin` middleware:** a `POST/PUT/PATCH/DELETE` whose `Origin` header isn't in `CORS_ORIGINS` gets `403`. This is CSRF protection (the ingress rewrites cookies to `SameSite=None`).
- **CORS:** explicit `CORS_ORIGINS` list with `allow_credentials=True`.
- **Startup:** creates indexes (`users.email` unique, `login_attempts.identifier`, `files(owner_type, owner_id)`), runs `seed_if_empty()` and calls `init_storage()`.

### 3.2 `db.py`
Loads `.env`, creates `AsyncIOMotorClient(MONGO_URL)`, and exports `db = client[DB_NAME]`.

### 3.3 `models.py`
Shared Pydantic models and helpers:
- `now_iso()` returns a UTC ISO string; `new_id()` returns a UUID4 string. **IDs are UUID strings in the `id` field. Mongo's `_id` is always excluded with `{"_id": 0}`.**
- `UserCreate`, `UserPublic`, `LoginRequest`; `Branch`, `Purity`, `Category`, `DailyRate`
- `Item` (`ItemStatus`: `in_stock | sold | transferred | in_transit | with_karigar | scrapped`), `ItemCreate`
- `StockMovement` (`MovementType`: `receipt | sale | transfer_out | transfer_in | karigar_issue | karigar_return | scrap | adjustment | audit_variance`)
- `ScanLog`, `ScanRequest`, `AuditSession`, `AuditScan`, `AuditLogEntry`

### 3.4 `auth.py`
| Function | Purpose |
|---|---|
| `hash_password` / `verify_password` | bcrypt |
| `validate_password` | min 8 characters, at least one letter and one digit, else 400 |
| `make_access_token(user, tv)` | JWT `{sub, role, branch_id, typ:"access", tv, exp, iat}`, 15 min |
| `make_refresh_token(user, tv)` | JWT `{sub, typ:"refresh", tv}`, 7 days |
| `set_auth_cookies` / `clear_auth_cookies` | `swarna_access` (path `/api`) and `swarna_refresh` (path `/api/auth`), both `HttpOnly; Secure; SameSite=Lax` |
| `get_current_user(request)` | reads the access cookie, decodes it, loads the user, rejects inactive users and `tv != user.token_version` |
| `require_roles(*roles)` | dependency factory, 403 when the role isn't allowed |
| `enforce_branch(user, branch_id)` | 403 unless the user is admin or `user.branch_id == branch_id` |

### 3.5 `audit.py`
`log_event(entity, action, entity_id, user_id, branch_id, diff)` appends to `audit_log`. Each entry stores `prev_hash` (the previous entry's hash) and `hash = sha256(canonical JSON incl. prev_hash)`, forming a tamper-evident chain.

### 3.6 `seed.py`
Idempotent startup seed:
- Admin from `ADMIN_EMAIL` / `ADMIN_PASSWORD`, created only if missing (the password is never overwritten on restart).
- Two sample branches, five purities (24K, 22K916, 18K, 925, PT950), six categories (HSN 7113/7114/7118, 3% GST) and today's rates, each only if its collection is empty.

### 3.7 `storage.py`
- `init_storage()` exchanges `EMERGENT_LLM_KEY` for a storage key (cached in the process).
- `put_object(path, data, content_type)` and `get_object(path)`, with one automatic re-init and retry on 404 (expired key).
- Paths: `swarnaerp/{owner_type}/{owner_id}/{uuid}.{ext}` and `swarnaerp/lookbook/{branch_id}/{uuid}.png`.

### 3.8 `invoice_pdf.py`
`build_invoice_pdf(bill, branch) -> bytes` creates an A4 black-and-white tax invoice:
- Header with branch name (Cormorant), address, GSTIN, state code, invoice number and date.
- Bill-to block, place of supply, supply type (intra-state CGST+SGST or inter-state IGST) and payment mode.
- Line table: Item/HUID, HSN, purity, gross, net, rate per gram, metal value, making, taxable.
- Totals: taxable, CGST/SGST or IGST, round off, invoice total.
- Old gold section (if any), then "Less old gold" and "Net payable".
- Amount in words (Indian system: crore, lakh, thousand), declaration and signatory.
- `_m()` formats with Indian digit grouping (1,23,456.00).

### 3.9 `whatsapp.py`
- `WhatsAppProvider` base: `send_text`, `send_document`, `send_image` (defaults to `send_document`).
- `MockProvider` (`mocked=True`) only logs messages.
- `PROVIDERS` registry plus `get_provider()`, chosen by `WHATSAPP_PROVIDER`.
- `normalize_phone()` keeps digits only, adds `91` to 10-digit numbers, and accepts 11–15 digits.
- `record_message(**fields)` writes to `whatsapp_messages` (the outbox).
- `send_invoice_message(bill, branch, actor_id)` builds the PDF, sends it as a document with a caption and records the result (`mocked | sent | failed | invalid_number`).

### 3.10 `lookbook.py`
- `build_card(title, subtitle, branch_name, footer, tiles) -> PNG bytes` makes a 1080×1350 card: navy header, 1 or 2-column grid (a lone last tile is centred), photo letterboxed with `ImageOps.contain`, name, purity/net weight and price.
- `inr(n)` formats rupees with Indian grouping.

### 3.11 Routers (all under `/api`)

**auth_router (`/auth`)**
| Method & path | Roles | Description |
|---|---|---|
| POST `/auth/login` | public | brute-force check, verify, set cookies, return `{user}` |
| POST `/auth/refresh` | refresh cookie | check `tv`, re-issue cookies |
| POST `/auth/logout` | any | clear cookies |
| GET `/auth/me` | any user | current user |
| GET `/auth/users` | admin, manager | admin sees all; a manager sees their own branch |
| POST `/auth/users` | admin | create staff (password policy; non-admins need a branch) |
| PATCH `/auth/users/{id}` | admin | name/role/branch/active; role/branch/active changes bump `token_version`; you can't demote or deactivate yourself |
| POST `/auth/users/{id}/reset-password` | admin | new hash and `token_version += 1` |

**masters_router**
| Path | Roles | Notes |
|---|---|---|
| GET/POST `/branches` | read any / write admin | non-admins only see their own branch |
| GET/POST `/purities` | write admin, manager | `code`, `label`, `metal`, `fineness` |
| GET/POST `/categories` | write admin, manager | `hsn_code`, `gst_rate` |
| GET/POST `/daily-rates`, GET `/daily-rates/latest` | write admin, manager | latest rate per (metal, purity) via aggregation |

**inventory_router**
| Path | Notes |
|---|---|
| GET `/items?branch_id&status&q` | branch-scoped; `q` searches tag/barcode/RFID/HUID |
| GET `/items/{id}`, POST `/items` | create checks uniqueness of tag/barcode/RFID, computes `net_wt = gross − stone`, writes a `receipt` movement |
| POST `/scan`, GET `/scan/lookup?code` | lookup by barcode, tag, RFID or HUID; other-branch items are hidden from non-admins |
| GET `/movements`, GET `/stock/summary?branch_id` | ledger and in-stock totals by purity |
| POST/GET `/audit/sessions`, POST `/audit/sessions/{id}/scan`, GET `/audit/sessions/{id}/variance`, POST `/audit/sessions/{id}/close` | stock audit |
| GET `/audit-log` | admin, manager, auditor |

**billing_router (`/bills`)**
| Path | Description |
|---|---|
| POST `/bills/quote` | prices the cart without saving (same body as create) |
| POST `/bills` | create bill (see flow 5.3) |
| GET `/bills?branch_id` | list |
| GET `/bills/old-gold?branch_id` | old-gold lots |
| GET `/bills/{id}/pdf` | invoice PDF |

Key helpers: `_making(type, value, net, metal)`, `_price_lines(items, overrides)`, `_price_old_gold(entries)`, `_totals(lines, branch_state, cust_state, old)`, `_compute(body, user)`.

**files_router (`/files`)**: POST (multipart `owner_type`, `owner_id`, `category`, `file`; max 25 MB; admin/manager/billing), GET list, GET `/{id}/download`, DELETE (soft delete; admin/manager).

**transfers_router (`/transfers`)**: POST create, GET list by branch (incoming and outgoing), GET `/branches` (destination names for all roles), GET `/{id}`, POST `/{id}/scan-out`, DELETE `/{id}/items/{item_id}`, POST `/{id}/dispatch`, POST `/{id}/scan-in`, POST `/{id}/receive`, POST `/{id}/cancel`. Write actions are for admin and manager only.

**whatsapp_router (`/whatsapp`)**: GET `/status`, POST `/invoices/{bill_id}`, POST `/broadcast` (admin/manager; audience `customers` = distinct phones from the branch's bills, or `custom`), GET `/messages?branch_id`. `resolve_recipients()` normalises and dedupes numbers, with a cap of 1000.

**lookbook_router (`/lookbook`)**: POST create (admin/manager; 1–6 in-stock items in the branch), GET `/photo-items?branch_id`, GET list, POST `/{id}/broadcast`.

---

## 4. Data model (MongoDB collections)

All documents use `id: str (uuid)` and ISO UTC timestamps. Weights are grams (3 decimals) and money is INR (2 decimals).

| Collection | Key fields | Written by |
|---|---|---|
| `users` | id, email (unique), name, role, branch_id, active, password_hash, token_version | auth |
| `login_attempts` | identifier (`ip:email`), count, locked_until | auth |
| `branches` | id, code, name, address, gstin, state_code, active | masters/seed |
| `purities` | id, code, label, metal, fineness | masters/seed |
| `categories` | id, name, hsn_code, gst_rate | masters/seed |
| `daily_rates` | id, rate_date, metal, purity_code, rate_per_gram, set_by | masters |
| `items` | id, tag_id, barcode, rfid_epc, huid, category_id, purity_id, gross_wt, stone_wt, net_wt, making_charge_type/value, status, branch_id, description | inventory, billing, transfers |
| `stock_movements` | id, movement_type, item_id or loose_lot_id, weight, branch_id, reference, user_id, created_at | append-only ledger |
| `scan_logs` | code, code_type, item_id, found, context, user_id | scan |
| `audit_sessions` / `audit_scans` | session status open/closed; scan status found/unknown/wrong_branch/wrong_status | audit |
| `audit_log` | entity, entity_id, action, user_id, branch_id, diff, prev_hash, hash | everything |
| `files` | id, owner_type (item/branch), owner_id, branch_id, category, original_filename, content_type, size, storage_path, is_deleted | files, lookbook |
| `bills` | id, bill_no, branch_id, customer_*, payment_mode, lines[], subtotal, cgst, sgst, igst, round_off, grand_total, old_gold[], old_gold_total, net_payable, whatsapp_status | billing |
| `counters` | `_id: "bill:{branch}"` or `"transfer:{branch}"`, seq | billing, transfers |
| `old_gold_lots` | id, bill_id, branch_id, description, metal, fineness, gross/stone/net/fine_wt, deduction_pct, value, status | billing |
| `transfers` | id, transfer_no, from/to_branch_id, status, items[{item_id, tag_id, net_wt, received}], unexpected_codes, missing_item_ids, timestamps | transfers |
| `whatsapp_messages` | kind (invoice/broadcast/lookbook), to, text, status, provider, campaign_id, bill_id/lookbook_id, branch_id | whatsapp |
| `lookbooks` | id, branch_id, title, subtitle, item_ids, file_id | lookbook |

Item status lifecycle:
```
receipt → in_stock ──bill──▶ sold
            │  ▲
   dispatch │  │ receive (branch_id changes to destination)
            ▼  │
        in_transit  (stays in_transit if never scanned in → flagged missing on the transfer)
```

---

## 5. Key data flows

### 5.1 Login and session
1. `POST /api/auth/login {email, password}`.
2. If `login_attempts[ip:email].locked_until > now`, return 429.
3. On a bad password, increment the count; at 5 failures lock for 15 minutes; log `login_failed`; return 401.
4. On success, clear attempts, set the `swarna_access` and `swarna_refresh` cookies, log `login`, and return `{user}`.
5. The frontend stores **only the user profile** (`swarna_user`) for first paint, then confirms it with `GET /auth/me`.
6. Any 401 triggers the axios interceptor, which makes **one shared** `POST /auth/refresh` (the promise is reused for 1.5 s) and retries the request. If refresh fails, it clears the profile and redirects to `/login`.
7. Admin changes to a user's role, branch, active flag or password bump `token_version`, so that user's existing cookies fail at the next request.

### 5.2 Scanning
- **USB / RFID wedge:** the reader types into a focused `<input>` and presses Enter, which submits the form and calls the handler.
- **Camera:** `CameraScanButton`, then `Html5Qrcode.getCameras()`; a rear camera is preferred and the last choice is remembered in `localStorage.swarna_camera`. Decoded text calls `onDetect(code)`. Repeats of the same code within 1.5 s are ignored. In `continuous` mode the dialog stays open.
- The same `onCode` handler serves both inputs on Scan Lookup, Billing and Stock Audit (and transfer scan-in/out).

### 5.3 Billing (including old gold)
```
scan → GET /scan/lookup → client cart
cart/overrides/state/old_gold change → POST /bills/quote (debounced 250 ms) → totals preview
Generate → POST /bills
  _compute: enforce branch → load items → all in branch & in_stock?
            → _price_lines: latest rate per purity; metal = net × rate
                            making: per_gram = v×net | percent = metal×v% | fixed = v
                            taxable = metal + making; gst_rate from category (default 3%)
            → _price_old_gold: per fine gram = latest rate of highest-fineness purity of that metal ÷ fineness
                               value = (gross−stone) × fineness × per_fine × (1 − deduction%)
            → _totals: tax = Σ taxable×gst%; inter-state if customer state ≠ branch state → IGST else CGST/SGST split
                       grand = round half up(subtotal + tax); old_total = rounded Σ old values
                       old_total > grand → 400; net_payable = grand − old_total
  sell: per item update_one({id, status:"in_stock"} → "sold"); if any fails → roll back earlier ones → 409
  bill_no = {branch code}-{seq:05d} from counters (atomic $inc)
  insert bill; sale movements; old_gold_lots + receipt movements; audit log
  phone present → send_invoice_message (never fails the bill) → whatsapp_status
```

### 5.4 Branch transfer
1. **Create** (from-branch manager or admin): `TR-{code}-{seq:04d}`, status `draft`.
2. **Scan-out:** the item must be in the from branch, `in_stock`, and not on another draft.
3. **Dispatch:** each item is conditionally updated from `in_stock` to `in_transit` (rolled back on any conflict). Writes `transfer_out` movements and sets status `in_transit`.
4. **Scan-in** (to-branch manager or admin): marks a manifest line `received`; codes not on the manifest go into `unexpected_codes` and return 404.
5. **Receive:** items that were scanned in and are still `in_transit` become `in_stock` with `branch_id = to`, and get `transfer_in` movements. If nothing is missing the status is `received`; otherwise it is `received_with_variance` with `missing_item_ids`. Late scan-in followed by receive again is allowed.

### 5.5 Files
Upload (multipart): resolve the owner's branch → `enforce_branch` → size ≤ 25 MB → `put_object` (in a thread) → metadata in `files` → audit. Downloads go through the backend (`/files/{id}/download`, auth-checked) and are never public URLs. Deletes are soft (`is_deleted`).

### 5.6 Lookbook
Pick 1–6 in-stock items → `_price_lines` → price incl. GST, rounded → first image file per item from storage → `build_card` → PNG to storage plus a `files` record (category `lookbook`) → `lookbooks` doc → broadcast with `provider.send_image` per recipient → outbox.

### 5.7 Stock audit
Start session → scan codes (each classified found/unknown/wrong_branch/wrong_status) → variance = expected in-stock items of the branch minus scanned-found, plus the unknown and wrong lists → close.

---

## 6. Security model

| Concern | Implementation |
|---|---|
| Passwords | bcrypt; policy of 8+ characters with letters and digits |
| Sessions | httpOnly Secure cookies; 15-minute access token, 7-day refresh token (refresh cookie only sent to `/api/auth`) |
| Revocation | `token_version` claim (`tv`) checked on every request and refresh |
| Brute force | 5 failures per IP+email, then a 15-minute lockout (429) |
| CSRF | Origin allow-list for unsafe methods, plus CORS with explicit origins |
| Authorisation | `require_roles` per route; `enforce_branch` for branch-owned data; non-admins can't see other branches, items, bills or files |
| Self-protection | an admin can't demote or deactivate their own account |
| Concurrency | conditional status updates prevent double-selling or double-dispatching an item |
| Audit | hash-chained `audit_log` |
| Files | private storage, served only through authenticated endpoints, 25 MB limit |
| Secrets | `.env` only (never committed); `JWT_SECRET`, `ADMIN_*`, `EMERGENT_LLM_KEY`, provider credentials |

Known gaps: no server-side refresh-token denylist (logout clears cookies only); no rate limiting beyond login; no field-level validation of GSTIN/HUID formats yet.

---

## 7. Frontend architecture

- **`App.js`:** `AuthProvider` → `BrowserRouter`; `Protected` guard (optional `roles`); routes under `Layout`.
- **`AuthContext`:** `user`, `login`, `logout`, `branches`, `branchId` (selected branch, saved in `localStorage.swarna_branch`). Non-admins are forced to their own branch.
- **`Layout`:** sidebar (role-filtered nav), top bar with branch switcher, live rate ticker, theme toggle (`localStorage.swarna_theme`) and user menu.
- **Pages** (one file per screen): Dashboard, Billing, Inventory, ScanLookup, StockAudit, Transfers, LabelPrint, Documents, WhatsApp, Lookbook, Masters, Staff, AuditLog, Login.
- **Shared components:** `CameraScanner` (`CameraScanButton`), `FileManager` (upload/list/thumbnail/download/delete for any owner), `OldGoldCard`.
- **Binary data:** PDFs, images and lookbook PNGs are fetched with `responseType: "blob"` (so cookies apply) and shown through `URL.createObjectURL`.
- **Design tokens** (`index.css`): `--bg --surface --panel --line --text --text-2 --text-muted --brand --brand-fg --gold --gold-text --gold-soft --success --warning --danger --info`, with light and `.dark` variants. The shadcn HSL tokens (`--primary`, `--border`, …) are kept separate. Fonts: Inter (with tabular numbers in `.font-num`, td, th), JetBrains Mono (`.font-mono`) and Cormorant Garamond (`.font-serif-brand`).
- **Testing hooks:** interactive elements carry `data-testid` attributes in kebab-case.

---

## 8. Extending the system

**Add an API module**
1. Create `backend/routers/x_router.py` with `router = APIRouter(prefix="/x")`.
2. Protect each route with `Depends(get_current_user)` or `require_roles(...)`, and call `enforce_branch`.
3. Define Pydantic request and response models; query with `{"_id": 0}`.
4. For stock changes, write a `StockMovement` and use conditional status updates.
5. Call `log_event(...)` for user actions.
6. Include it in `server.py` with `api_router.include_router(...)`.

**Add a screen**
1. Create `src/pages/X.jsx` (default export).
2. Add a route in `App.js` and a nav entry in `Layout.jsx`'s `NAV` (with `roles` if it's restricted).
3. Use `api` and `errMsg`, shadcn components and the design tokens.

**Planned modules that fit the current model:** customer master (KYC/PAN), estimates, split payments, purchases (`receipt` movements), karigar issue/return (`with_karigar` status, karigar movements), schemes/bookings, refiner dispatch for `old_gold_lots`, transit write-off (`adjustment` movement with manager approval), GST reports (GSTR-1 export from `bills`).

---

## 9. Operations

- **Health:** `GET /api/health`.
- **Logs:** standard Python logging (`swarnaerp.*` loggers). Mock WhatsApp sends are logged as `[MOCK WhatsApp]`.
- **Indexes:** created at startup. Add indexes for heavy queries (for example `items.branch_id+status`, `bills.branch_id+created_at`) as data grows.
- **Backups:** use MongoDB-native backups (mongodump or managed snapshots). Object storage holds the file binaries; the `files` collection holds their metadata.
- **Deployment:** set every backend env var and include every serving domain in `CORS_ORIGINS`, or write requests will be rejected with 403.
