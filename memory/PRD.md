# SwarnaERP — PRD

## Original problem
Multi-branch Indian retail Gold/Jewellery ERP (spec asked for Flutter + NestJS + PostgreSQL; built as web app on React + FastAPI + MongoDB per user's "choose best" answer). Modules: masters, inventory, billing/GST, old-gold, purchases, scrap, karigar, customers/schemes, reports, admin. User also wants auto WhatsApp messages for invoices and new-launch broadcasts, using their own provider (their tech team will connect it later).

## User choices
- Phase 1 only: Auth/RBAC, Masters, Inventory, Scan, Labels
- JWT auth + RBAC (admin/manager/billing/auditor) + branch scoping
- Scanning: camera (incl. external) + USB keyboard-wedge barcode/RFID readers
- Server-side GST PDF via ReportLab (Phase 2, with billing)
- WhatsApp: pluggable, own provider later

## Architecture
- Backend: FastAPI routers (auth, masters, inventory), bcrypt + JWT access/refresh, append-only stock_movements, hash-chained audit_log, idempotent seed
- Frontend: React + shadcn, Cormorant/Manrope/JetBrains Mono, champagne-gold light theme + dark toggle

## Implemented (2026-06)
- Login/refresh/me, admin create-user API (no UI yet)
- Branches, purities, categories (HSN/GST), daily rates (latest per purity)
- Tagged items (unique tag/barcode/RFID, net weight calculated), stock summary, movements ledger
- Scan lookup (USB wedge, duplicate-scan debounce, warnings for other-branch/wrong-status items)
- Stock audit sessions: scan → found/unknown/wrong_branch/wrong_status, variance, close
- TSPL/ZPL label payload + live tag preview (download)
- Audit log viewer

## Not done / known gaps
- Camera scanning not built (button only focuses the input)
- RBAC for non-admin roles not tested end-to-end; no Users management UI
- Frontend flows only partly checked (screenshots: login, dashboard, add item, scan)

## Backlog
- P0: Users UI + non-admin RBAC test, camera scanner (zxing), billing/GST invoice + ReportLab PDF
- P1: WhatsApp provider interface (invoice send, broadcasts), old-gold exchange, stock transfers
- P2: purchases, karigar, schemes, reports, backups
