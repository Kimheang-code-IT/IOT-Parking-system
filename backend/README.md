# IOT Parking — Backend API & Research Results

**For instructor review** · Course: Basic Electronic · Project: Smart IoT Parking System

Full chapters **1 (Introduction)** and **2 (Related Work)** are in [`../docs/RESEARCH_REPORT.md`](../docs/RESEARCH_REPORT.md).

---

## 4. Results and Discussion

This section reports what was **built**, **tested**, and **observed** on the backend (`FastAPI` + `SQLite`) that powers the RFID IoT gates, payment flow, and Nuxt dashboard.

### 4.1 System Delivered

| Layer | Technology | Role in results |
|-------|------------|-----------------|
| API server | Python 3.11+, FastAPI, Uvicorn | Business rules, REST, OpenAPI `/docs` |
| Database | SQLite `data/iot_parking.db` (PostgreSQL-ready) | Sessions, invoices, `device_commands`, `rfid_cards`, `rfid_scan_events`, payments |
| RFID identity | `rfid_service` | Card → plate registry, scan audit, duplicate protection |
| Gate logic | `gate_command_service`, `gate_lane_service`, `gate_exit_auto_service` | Entry/exit gate commands with ack + expiry |
| Security on ticket | HMAC `verifyHash` in barcode | `IOT-PARKING:plate\|invoice\|hash` |
| Payment | `payment_service`, ABA mock/PayWay | KHQR image + webhook → invoice **Paid** → exit command |
| IoT | `iot` + `rfid` routers | ESP32 polls `commands/next`, acks, gate events |
| Firmware | `iot/` PlatformIO (Arduino C++) | RC522 RFID gates + fail-safe state machine, 27 host unit tests |
| Proof of work | `tests/` (pytest) + `scripts/test_integration.py` | 34 automated pytest tests + 34 live checks against running API |

**Fee policy (verified in tests):**

- Parking **under 1 hour** → **$1.00** minimum (`MINIMUM_FEE`)
- **1 hour or more** → billed hours (rounded **up**) × **$2.00/h** (`RATE_PER_HOUR`)

### 4.2 Test Method

1. Start API: `.\scripts\run_dev.ps1` (from `backend/`) or `..\scripts\run_backend.ps1` (from repo root).
2. Confirm health: `GET http://127.0.0.1:8000/health` → `{"status":"ok"}`.
3. Run the isolated pytest suite (no running server needed):

```powershell
cd backend
pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

4. Run the live integration script against the running API:

```powershell
cd backend
python -m scripts.test_integration
```

**Pass criteria:** `34 passed` (pytest) and `=== Result: 34/34 passed ===` (live script).

### 4.3 Integration Test Results (Expected)

| # | Area | Result expected |
|---|------|-----------------|
| 1 | Health | HTTP 200, `status: ok` |
| 2–6 | Dashboard endpoints (stats, trends, charts) | HTTP 200, JSON body |
| 7–9 | Parking list, invoices list, bank info | HTTP 200, data present |
| 10–12 | RFID card register + block | Card created, status `Blocked` |
| 13–14 | RFID entry scan | `authorized: true`, session + invoice + receipt file |
| 15 | Duplicate scan | `duplicate: true`, no second session |
| 16–17 | Unknown / blocked card | `success: false` with reason, logged in scan history |
| 18–19 | Entry gate command | `ENTRY_APPROVED` queued, acked `completed` |
| 20–22 | Payment page + ABA QR + parking DB | Amount, `data:image` QR, new DB row |
| 23 | RFID exit scan (unpaid) | `paymentPending: true`, exact fee, **no gate command** |
| 24 | Gate locked check | No `EXIT_APPROVED` before payment |
| 25–27 | Payment webhook → gate command → ack | `EXIT_APPROVED` after paid, acked |
| 28–29 | Session status + operator open | `canOpenGate: true`, open succeeds |
| 30 | Invoice in DB | `status: Paid` |
| 31–32 | Scan history + gate activity | Events recorded, command states visible |
| 33 | Legacy IoT entry-scan | Still supported |
| 34 | CORS for `localhost:3000` | Allow-Origin suitable for frontend |

The pytest suite additionally covers **disconnected devices** (commands expiring
before delivery), **late acknowledgements**, wrong device tokens, ack of
unknown commands, fee calculation for a 2 h 05 m stay ($6.00), and
pay-before-scan re-entry at the exit gate.

### 4.4 Entry Flow — Observed Behaviour

| Step | API / action | Observed result |
|------|--------------|-----------------|
| 1 | `POST /api/rfid/entry-scan` (card UID, device auth) | Card resolved to plate; `parking_sessions` (Active) + `invoices` (Pending) created |
| 2 | Print data | Text receipt with `verifyHash` saved under `data/receipts/` |
| 3 | Command queue | `ENTRY_APPROVED` for `ENTRY_GATE_01` with session/invoice payload |
| 4 | ESP32 | Polls `commands/next`, opens the servo, acks, reports `entry_car_passed` / `entry_gate_closed` |
| 5 | Safety | The ultrasonic sensor alone never opens the gate; approval expiry prevents stale opens |

### 4.5 Exit Flow — Observed Behaviour

| Step | API / action | Observed result |
|------|--------------|-----------------|
| 1 | `POST /api/rfid/exit-scan` | Active session resolved from the card's plate; fee calculated and stored |
| 2 | Unpaid | Response `paymentPending: true` + amount; no gate command is queued |
| 3 | Payment | ABA webhook / Payment page verify marks invoice **Paid** and closes the session |
| 4 | Gate | `EXIT_APPROVED` queued automatically; ESP32 opens the exit servo |
| 5 | Operator | `POST /api/iot/open-gate` succeeds only for Completed + Paid sessions |
| 6 | Failure cases | Unknown/blocked cards and unpaid scans never open the gate; reasons logged |

### 4.6 Frontend Coupling (Discussion)

The backend exposes camelCase JSON for Nuxt:

- `GET /api/payment/active-session` — payment page amount and plate
- `GET /api/payment/aba-qr` — KHQR image for `AppKhqrCard.vue`
- `GET /api/rfid/cards`, `/api/rfid/scans`, `/api/rfid/gate-activity` — RFID page
- `GET /api/parking`, `/api/invoices` — tables with live sync via revision bumps

**Design result:** the dashboard does **not** call gate-open device endpoints;
only IoT gates execute gate commands (plus the paid-session operator endpoint),
matching the safety objective in the research proposal.

### 4.7 Firmware Hardware-in-the-Loop Results

| Item | Observation |
|------|-------------|
| Firmware | `iot/` PlatformIO (Arduino C++), roles `entry_gate` / `exit_gate` |
| Build | `pio run` succeeds for both roles (RAM ~14%, flash ~66%) |
| Host tests | 27/27 Unity tests pass (`pio test -e native`) |
| Backend link | ESP32 polls `commands/next`, posts acks + gate events; approvals expire server-side |
| Fail-safe | Passage-sensor blocked/fault ⇒ gate holds open + `gate_fault` event (unit-tested) |

Physical wiring checks (RC522 read distance, servo, real payment) are listed in
the root README validation report as **unverified on real hardware** until the
gates are built.

### 4.8 Answers to Research Questions

| Question | Finding |
|----------|---------|
| **RQ1** Three-tier IoT + API + web | Supported: 34 pytest + 34 live checks; gates are not controlled from the dashboard |
| **RQ2** Ticket/barcode integrity | Supported: HMAC `plate\|invoice\|hash` barcode still issued at entry; RFID is the primary identity |
| **RQ3** ABA KHQR gating | Supported: QR + webhook gate the exit command; mock mode for class demos |
| **RQ4** Backend-controlled gates | Supported: pending → delivered → acked/failed/expired lifecycle with ack + timeout tests |

### 4.9 Limitations

- RFID UIDs can be cloned — the card is an identifier, not production-grade authentication.
- SQLite is for **single-machine** demos; the schema is PostgreSQL-compatible.
- PayWay live keys not required when `ABA_PAY_USE_MOCK=true`.
- Physical printer/scanner drivers are simulated via file receipts and API fields.
- Hardware validation (RC522 reads, servo timing, passage sensor) is pending the physical build.

### 4.10 Conclusion (Backend)

The backend implements the full parking lifecycle: **RFID entry identification →
stored session/invoice → verifiable ticket → fee calculation → payment →
backend-controlled exit authorization + command acknowledgement**. Automated
test suites provide repeatable evidence for grading, and the ESP32 firmware
consumes the same API contracts the tests exercise.

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
- Tests: `pip install -r requirements-dev.txt` → `python -m pytest`
- IoT headers: [docs/IOT_DEVICES.md](docs/IOT_DEVICES.md)
- Firmware: [../iot/README.md](../iot/README.md)
- Full run guide: [../README.md](../README.md)
- Research chapters 1–2: [../docs/RESEARCH_REPORT.md](../docs/RESEARCH_REPORT.md)
