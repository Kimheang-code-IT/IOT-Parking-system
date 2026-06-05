# IOT Parking — Backend API & Research Results

**For instructor review** · Course: Basic Electronic · Project: Smart IoT Parking System  

Full chapters **1 (Introduction)** and **2 (Related Work)** are in [`../docs/RESEARCH_REPORT.md`](../docs/RESEARCH_REPORT.md).

---

## 4. Results and Discussion

This section reports what was **built**, **tested**, and **observed** on the backend (`FastAPI` + `SQLite`) that powers the IoT gates, payment flow, and Nuxt dashboard.

### 4.1 System Delivered

| Layer | Technology | Role in results |
|-------|------------|-----------------|
| API server | Python 3.11+, FastAPI, Uvicorn | Business rules, REST, OpenAPI `/docs` |
| Database | SQLite `data/iot_parking.db` | Sessions, invoices, `device_commands`, payments |
| Gate logic | `gate_trigger_service`, `gate_lane_service` | Entry OCR trigger, exit barcode trigger |
| Security on ticket | HMAC `verifyHash` in barcode | `IOT-PARKING:plate\|invoice\|hash` |
| Payment | `payment_service`, ABA mock/PayWay | KHQR image + webhook → invoice **Paid** |
| IoT | `iot` router, command queue | ESP32 polls `commands/next`, acks, gate events |
| Proof of work | `scripts/test_integration.py` | 24 automated checks against running API |

**Fee policy (verified in tests):**

- Parking **under 1 hour** → **$1.00** minimum (`MINIMUM_FEE`)
- **1 hour or more** → billed hours (rounded **up**) × **$2.00/h** (`RATE_PER_HOUR`)

### 4.2 Test Method

1. Start API: `.\scripts\run_dev.ps1` (from `backend/`) or `..\scripts\run_backend.ps1` (from repo root).  
2. Confirm health: `GET http://127.0.0.1:8000/health` → `{"status":"ok"}`.  
3. Run integration suite:

```powershell
cd backend
python -m scripts.test_integration
```

4. Optional Wokwi-aligned script (same entry/exit triggers as green/blue buttons):

```powershell
powershell -File scripts\test_wokwi_flow.ps1
```

**Pass criterion:** `=== Result: 24/24 passed ===` (or 23/24 if exit block skipped due to missing prior entry data).

### 4.3 Integration Test Results (Expected)

When the API is running with default `.env` (from `.env.example`), the following **must pass**:

| # | Test | Result expected |
|---|------|-----------------|
| 1 | Health | HTTP 200, `status: ok` |
| 2–6 | Dashboard endpoints (stats, trends, charts) | HTTP 200, JSON body |
| 7 | Parking list | HTTP 200, `data` array |
| 8 | Invoices list | HTTP 200, `data` array |
| 9 | Bank info | HTTP 200, bank `name` set |
| 10 | Gate entry trigger (`source: simulator`) | `success: true`, `sessionId`, `invoiceId`, `verifyHash` |
| 11 | Receipt on disk | `printSavedPath` under `data/receipts/` |
| 12 | Legacy IoT entry-scan | HTTP 200 or 409 (duplicate handling) |
| 13 | Verify hash on ticket | Non-empty hash |
| 14 | Active session for payment page | Plate matches test plate |
| 15 | ABA QR generate | `qrImage` starts with `data:image`, status code `0` |
| 16 | Parking DB reflects entry | Search finds new row |
| 17 | Gate exit trigger + mock payment | `success: true`, fee ≥ $1.00 |
| 18 | Legacy exit-verify | `success: true` |
| 19 | Payment webhook | `success: true` |
| 20 | Session status | `canOpenGate: true`, payment paid |
| 21 | Open exit gate | `success: true` |
| 22 | Invoice in DB | `status: Paid` |
| 23 | Device command poll | HTTP 200 or 204 |
| 24 | CORS for `localhost:3000` | Allow-Origin suitable for frontend |

**Sample successful console tail:**

```text
=== Result: 24/24 passed ===
All systems connected. Open http://localhost:3000 and verify UI visually.
```

### 4.4 Entry Flow — Observed Behaviour

| Step | API / action | Observed result |
|------|----------------|-----------------|
| 1 | `POST /api/gate/entry/trigger` | Creates `parking_sessions` (Active) + `invoices` (Pending) |
| 2 | Print data | Code128 barcode + `verifyHash` generated |
| 3 | Receipt file | Text/barcode receipt saved (path in response) |
| 4 | Command queue | `ENTRY_APPROVED` for `GATE_SIM_01` (simulator) or `ENTRY_GATE_01` |
| 5 | Wokwi / ESP32 | Entry servo opens; LCD shows entry OK; auto-close after configured seconds |

### 4.5 Exit Flow — Observed Behaviour

| Step | API / action | Observed result |
|------|----------------|-----------------|
| 1 | Scan `IOT-PARKING:plate\|invoice\|hash` | Parsed; invoice loaded from DB |
| 2 | Fee calculation | Amount from duration + rate rules |
| 3 | Payment | Mock or ABA webhook sets invoice **Paid** |
| 4 | Gate | `EXIT_APPROVED` queued; exit servo opens on device |
| 5 | Failure cases | Wrong hash / unpaid → `EXIT_DENIED` (red LED + buzzer on simulator) |

### 4.6 Frontend Coupling (Discussion)

The backend exposes camelCase JSON for Nuxt:

- `GET /api/payment/active-session` — payment page amount and plate  
- `GET /api/payment/aba-qr` — KHQR image for `AppKhqrCard.vue`  
- `GET /api/parking`, `/api/invoices` — tables with live sync via parking revision bump on gate events  

**Design result:** Dashboard does **not** call gate-open endpoints; only lane IoT and `gate/*` triggers do—matching the safety objective in the research proposal.

### 4.7 Wokwi Hardware-in-the-Loop Results

| Item | Observation |
|------|-------------|
| Firmware | MicroPython `.bin` per `wokwi.toml` (not `main.py` as firmware) |
| Serial boot | `boot.py: MicroPython starting` → `Booting...` → I2C/LCD lines |
| Gateway | `wokwigw.exe` port **9011** → API at `host.wokwi.internal:8000` |
| Green button | Same as entry trigger test (simulator plate) |
| Blue button | Exit barcode + mock payment when `GATE_AUTO_MOCK_PAYMENT=true` |

### 4.8 Answers to Research Questions

| Question | Finding |
|----------|---------|
| **RQ1** Three-tier IoT + API + web | Supported: 24 integration checks; gates not controlled from dashboard |
| **RQ2** Barcode `plate\|invoice\|hash` | Supported: exit trigger resolves invoice without separate plate OCR |
| **RQ3** ABA KHQR gating | Supported: QR + webhook; mock mode for class demos |
| **RQ4** Wokwi parity | Supported: same endpoints as `test_wokwi_flow.ps1` and physical ESP32 poll |

### 4.9 Limitations

- OCR quality depends on webcam and Tesseract install (optional).  
- SQLite is for **single-machine** demos, not multi-site production.  
- PayWay live keys not required when `ABA_PAY_USE_MOCK=true`.  
- Physical printer/scanner drivers are simulated via file receipts and API fields.

### 4.10 Conclusion (Backend)

The backend successfully implements the parking lifecycle: **entry identification → stored session/invoice → verifiable ticket → payment → exit authorization → IoT command delivery**. Automated tests provide repeatable evidence for grading; Wokwi and lane scripts use the same API contracts.

---

## Developer Setup (short)

```powershell
pip install -r requirements.txt
copy .env.example .env
.\scripts\run_dev.ps1
```

- OpenAPI: http://127.0.0.1:8000/docs  
- Database: `data/iot_parking.db`  
- Reset data: `python scripts/reset_db.py` or `python scripts/reset_db.py --demo`  
- IoT headers: [docs/IOT_DEVICES.md](docs/IOT_DEVICES.md)  
- Full run guide: [../README.md#how-to-run](../README.md#how-to-run)  
- Research chapters 1–2: [../docs/RESEARCH_REPORT.md](../docs/RESEARCH_REPORT.md)
