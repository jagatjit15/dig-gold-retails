# SwarnaERP — PRD

## Original problem
Multi-branch Indian retail Gold/Jewellery ERP (spec asked for Flutter + NestJS + PostgreSQL; built as a web app on React + FastAPI + MongoDB per the user's "choose best" answer). Modules: masters, inventory, billing/GST, old-gold, purchases, scrap, karigar, customers/schemes, reports, admin. Auto WhatsApp for invoices + new-launch broadcasts via the user's own provider (their tech team plugs it in later).

## User choices
- JWT auth + RBAC (admin/manager/billing/auditor) + branch scoping
- Scanning: camera (phone/laptop/external) + USB keyboard-wedge barcode/RFID
- Server-side GST PDF (ReportLab)
- Files: item photos/documents + per-branch library; any type, max 25 MB; upload admin/manager/billing, delete admin/manager
- Sold items must leave inventory when a bill is generated
- Design: calm neutral base, navy primary #1F3A5F, gold only as accent; Inter UI with tabular numbers, Cormorant Garamond for brand/invoice, JetBrains Mono for codes, Noto Devanagari/Odia fallback; status shown with icon + label, not colour alone

## Architecture
- Backend routers: auth, masters, inventory/scan/audit, files (Emergent Object Storage), billing (quote/bill/PDF), whatsapp
- `whatsapp.py` provider slot (MockProvider default; WHATSAPP_PROVIDER env); `invoice_pdf.py` (B&W A4 tax invoice, Cormorant TTF in backend/fonts)
- Auth: bcrypt, access 15 min / refresh 7 days, token_version revocation, login lockout (5 tries / 15 min)

## Implemented
- 2026-06 Phase 1: auth, masters, daily rates, tagged inventory, scan lookup, stock audit + variance, TSPL/ZPL labels, audit log
- 2026-06 v0.2: file storage (item + branch library), billing counter (scan, making override, CGST/SGST vs IGST, round off, payment mode, sold-item locking, PDF invoice), WhatsApp outbox + broadcasts (MOCKED), staff accounts screen, camera scanning (html5-qrcode, camera picker), navy/gold re-theme. Tested: backend 17/17, all UI flows pass (iteration_2)
- 2026-06 v0.3: branch transfers (draft → scan-out → dispatch/in transit → scan-in → receive; missing items flagged, late scan-in to resolve; unexpected codes logged), old gold exchange on bills (fineness × net × fine rate − deduction, after GST, net payable, old_gold_lots + receipt movement, PDF section), launch lookbook (1080×1350 PNG card from item photos with weight + price incl. GST, stored in object storage, WhatsApp broadcast — MOCKED). Tested iteration_3: backend 8/8 after fixes, all UI flows pass

- 2026-06 code-review fixes: httpOnly cookie sessions (no tokens in localStorage), Origin check on write requests, explicit CORS list, admin seed from env, stable React keys, storage retry cleanup. Tested iteration_4: backend 39/39, all UI flows pass
- 2026-06 security audit fixes: file downloads forced to attachment unless png/jpeg/webp/gif/pdf (+CSP sandbox, nosniff), audit log branch-scoped, item search regex escaped, admin seed no longer overwrites password, CSRF requires Origin/Referer when cookies present, security headers, POST /scan hides other-branch items, atomic 10 broadcasts/hour/branch quota, audit-log write lock. Tested iteration_5: 36/36 security tests, UI flows pass

## Known gaps
- Audit hash-chain lock is per process; multi-instance deploys need a unique index on prev_hash + retry (one historic fork exists)
- WhatsApp is MOCKED until a provider is connected
- Real camera decoding not verifiable in headless tests
- Logout clears cookies only; a stolen refresh cookie stays valid up to 7 days (no server-side revocation on logout)
- Web fonts come from Google Fonts, so they need internet (not bundled for offline use)

## Backlog
- P0: connect real WhatsApp provider; customer master (KYC, PAN for high-value sales)
- P1: write-off flow for transfer items that never arrive; old gold lots → refiner/scrap; estimates, split payments
- P2: purchases, karigar job work, schemes/bookings, GST reports (GSTR-1 export), backups
