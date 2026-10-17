# IOT Parking System

Smart parking management — **ESP32 RFID gates** (entry/exit), FastAPI backend with invoicing, **ABA KHQR payments**, a staff dashboard (Nuxt UI), and full test suites for firmware and backend.

---

## Overview

The **IOT Parking System** automates a parking lot from entry to exit:

1. **Entry** — a car triggers the approach sensor; the LCD asks the driver to **tap an RFID card**. The ESP32 posts the card UID to FastAPI; the backend resolves the registered plate, creates the parking session + invoice, saves the entry receipt, and queues **`ENTRY_APPROVED`**. The gate servo opens only then; a **passage safety sensor** watches the car cross and the gate closes.
2. **Parking** — staff see occupancy, history, and invoices on the web dashboard. Cards are registered / blocked on the **RFID** page.
3. **Exit** — the driver taps the same card at the exit gate: FastAPI finds the active session, **calculates the fee** and checks payment. The gate opens (**`EXIT_APPROVED`**) only after **ABA KHQR / verified payment**; if unpaid, the LCD shows the amount and the gate stays locked until payment completes.

| Layer | Role | Users |
|-------|------|-------|
| **Edge (IoT)** | ESP32 RFID gates: RC522 reader, servo, LCD, LEDs, ultrasonic sensors | Drivers (indirect), lane hardware |
| **Server** | FastAPI, SQLite (PostgreSQL-ready), gate command queue, payment webhooks | ESP32 gates, dashboard |
| **Web dashboard** | Cards, analytics, parking history, KHQR payment display, invoices | Staff / admin |

**Design rules**

- The dashboard does **not** open gates — only the IoT gates execute gate commands (operators can open the exit gate via the device endpoint once the session is paid).
- The ultrasonic sensor alone never opens a gate — authorization always comes from an RFID scan + the backend.
- **Fee:** under 1 hour → $1.00 minimum; 1 hour or more → billed hours (rounded up) × $2.00/hour.
- **Security:** an RFID card UID is an identifier, not a secret (MIFARE UIDs can be cloned). Fine for this local/educational system — not sufficient authentication for production use (see [Security notes](#security-notes)).

---

## Hardware & Wiring

Full wiring guide and BOM: **[`iot/README.md`](iot/README.md)**.

| Component | Pin (ESP32) | Note |
|-----------|-------------|------|
| HC-SR04 **approach sensor** TRIG / ECHO | 5 / 18 | existing wiring kept |
| Gate **servo** signal | 13 | 50 Hz PWM, 5 V supply |
| **Green / red LED** | 25 / 26 | gate state feedback |
| **16x2 LCD** I²C SDA / SCL | 21 / 22 | addr `0x27` |
| **RC522 RFID**: SS / SCK / MOSI / MISO / RST | 4 / 14 / 23 / 19 / 27 | **3.3 V only**, SPI remapped to avoid GPIO 5/18 |
| HC-SR04 **passage safety sensor** TRIG / ECHO | 32 / 33 | fail-safe: gate never closes over a car |
| LCD shows | `Scan card…`, `Checking card`, `Payment due $x.xx`, `Gate open`, `Access denied`, `FAILSAFE open` | |

---

## How to Run

> **Docker option:** `infrastructure/` contains a complete local stack
> (PostgreSQL + FastAPI + Nuxt + nginx reverse proxy) — see
> [`infrastructure/README.md`](infrastructure/README.md). Everything below is
> the manual/dev workflow.

Open a terminal in the **repository root** (`IOT-Parking/`). Commands assume **PowerShell** on Windows.

### Prerequisites

| Tool | Notes |
|------|--------|
| Python **3.11+** | Backend + tests |
| Node.js + **pnpm** | Dashboard (`frontend/`) |
| **PlatformIO** (VS Code extension or CLI) | ESP32 firmware (`iot/`) |
| **Host C++ compiler** (optional) | `pio test -e native` on the PC, e.g. `winget install MartinStorsjo.LLVM-MinGW.UCRT` |
| ESP32 DevKit + RC522 + servo + LCD + HC-SR04 ×2 | The physical gates |

### One-time setup

```powershell
cd IOT-Parking

python -m venv .venv
.\.venv\Scripts\Activate.ps1

cd backend
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

cd ..\frontend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
pnpm install

cd ..\iot
Copy-Item include\parking_secrets.example.h include\parking_secrets.h
# edit include\parking_secrets.h: Wi-Fi, API LAN IP, device tokens
```

### Run commands (pick what you need)

Use **separate terminals** — keep each process running.

| # | What | Command | Open in browser |
|---|------|---------|-----------------|
| **1** | **API** (required) | From repo root: `.\scripts\run_backend.ps1` — or from `backend/`: `uvicorn app.main:app --host 0.0.0.0 --port 8000` | http://127.0.0.1:8000/docs |
| **2** | **Dashboard** | `cd frontend` → `pnpm dev` | http://localhost:3000 |
| **3** | **Entry gate** | `cd iot` → `pio run -e entry_gate -t upload --upload-port COMx` | Serial monitor 115200 |
| **4** | **Exit gate** | `cd iot` → `pio run -e exit_gate -t upload --upload-port COMy` | Serial monitor 115200 |

Use `--host 0.0.0.0` so the ESP32s can reach the API over the LAN, and allow port **8000** through the Windows Firewall (private networks).

**Health check:**

```powershell
curl http://127.0.0.1:8000/health
```

### Demo without hardware

Use **mock/simulated lanes** against the live API (no ESP32 required):

```powershell
# Register a card (dashboard API)
curl -X POST http://127.0.0.1:8000/api/rfid/cards -H "Content-Type: application/json" `
  -d '{\"cardUid\":\"04A1B2C3\",\"licensePlate\":\"2A-1234\",\"vehicleType\":\"Car\"}'

# Simulate an entry tap (device-authenticated)
curl -X POST http://127.0.0.1:8000/api/rfid/entry-scan -H "Content-Type: application/json" `
  -H "x-device-code: ENTRY_GATE_01" -H "x-device-token: secret-entry-token" `
  -d '{\"deviceCode\":\"ENTRY_GATE_01\",\"cardUid\":\"04A1B2C3\"}'
```

Or the full automated flows: `python -m scripts.test_integration` (see [Tests](#tests)).

---

## Whole Project Flow

```mermaid
flowchart TB
    subgraph Entry["1 — Entry (RFID)"]
        E1[Car arrives at entry] --> E2[Approach sensor detects car]
        E2 --> E3[LCD: Scan card]
        E3 --> E4[RC522 reads card UID]
        E4 --> E5[POST /api/rfid/entry-scan]
        E5 --> E6[Backend: card to plate, session + invoice + receipt]
        E6 --> E7[ENTRY_APPROVED queued]
        E7 --> E8[ESP32 polls command, opens servo]
        E8 --> E9[Passage sensor sees car pass, gate closes]
    end

    subgraph Park["2 — Parked"]
        P1[Session Active]
        P2[Dashboard: cards, stats, parking, invoices]
        P1 --- P2
    end

    subgraph Exit["3 — Exit (RFID + payment)"]
        X1[Car at exit, LCD: Scan card] --> X2[POST /api/rfid/exit-scan]
        X2 --> X3[Backend: active session + fee]
        X3 --> X4{Paid?}
        X4 -->|No| X5[LCD shows fee - gate locked]
        X6[ABA KHQR webhook / dashboard verify] --> X4
        X4 -->|Yes| X7[EXIT_APPROVED queued]
        X7 --> X8[ESP32 opens exit servo]
    end

    E9 --> Park
    Park --> X1
```

---

## Entry Flow

```mermaid
sequenceDiagram
    autonumber
    participant Car
    participant ESP as ESP32 entry gate
    participant API as FastAPI
    participant DB as SQLite
    participant S as Servo

    Car->>ESP: Approach sensor detects car
    ESP->>ESP: LCD "Scan card to enter"
    Car->>ESP: RFID card tapped (RC522)
    ESP->>API: POST /api/rfid/entry-scan (device auth)
    API->>DB: rfid_cards lookup (status Active)
    API->>DB: parking_sessions Active + invoices Pending + receipt file
    API-->>ESP: authorized + sessionId/invoiceId
    API->>DB: Queue ENTRY_APPROVED for ENTRY_GATE_01
    ESP->>API: GET /api/iot/commands/next
    API-->>ESP: ENTRY_APPROVED
    ESP->>S: Open gate 90°
    ESP->>API: POST /api/iot/commands/ack (completed)
    Car->>ESP: Passage sensor sees the car cross
    ESP->>API: POST /api/iot/gate/event entry_car_passed + entry_gate_closed
    ESP->>S: Close gate 0°
```

- Unknown / blocked cards are denied with a reason on the LCD and logged in `rfid_scan_events`.
- Duplicate taps are suppressed twice: on the firmware (scan gate) and on the backend (cooldown window).
- A car whose card already has an **active session** gets the entry gate re-opened for that session instead of a duplicate session.
- The thermal receipt (barcode + verify code) is saved to `backend/data/receipts/`; the customer keeps the entry ticket for the invoice.

## Exit Flow

```mermaid
sequenceDiagram
    autonumber
    participant Car
    participant ESP as ESP32 exit gate
    participant API as FastAPI
    participant Bank as ABA KHQR / dashboard
    participant S as Servo

    Car->>ESP: Approach sensor detects car
    ESP->>ESP: LCD "Scan card to exit"
    Car->>ESP: RFID card tapped
    ESP->>API: POST /api/rfid/exit-scan
    API->>API: Active session by card plate + fee calculation

    alt Already paid
        API->>API: Queue EXIT_APPROVED
        API-->>ESP: authorized
    else Payment pending
        API-->>ESP: paymentPending + amount
        ESP->>ESP: LCD "Payment due $x.xx"
        Car->>Bank: Pay via ABA KHQR / Payment page
        Bank->>API: POST /api/payment/webhook (invoice -> Paid)
        API->>API: Queue EXIT_APPROVED automatically
    end

    ESP->>API: GET /api/iot/commands/next
    API-->>ESP: EXIT_APPROVED
    ESP->>S: Open exit gate
    ESP->>API: gate events + command ack
```

- The exit gate is **backend-controlled**: it opens on `EXIT_APPROVED` only, which is queued exclusively for paid/authorized sessions.
- Payment paths: ABA KHQR webhook (`POST /api/payment/webhook`), dashboard Payment page verify (`POST /api/payment/verify`), or the dev mock helper (`POST /api/gate/exit/mock-payment`).
- Operators can open the exit gate device-side (`POST /api/iot/open-gate`) only after the session is **Completed + Paid**.
- Paid-first drivers can still tap at the gate: a recent paid invoice re-queues the approval (30-minute window).

## Payment Flow

```mermaid
sequenceDiagram
    autonumber
    participant Customer
    participant UI as Payment page
    participant API as FastAPI
    participant Bank as ABA Mobile
    participant ESP as Exit gate ESP32

    Customer->>UI: Plate + ticket verify code (or exit scan already set the fee)
    UI->>API: GET /api/payment/active-session
    API-->>UI: plate, duration, amount
    UI->>API: GET /api/payment/aba-qr
    API-->>UI: KHQR image
    Customer->>Bank: Pay in ABA app
    Bank->>API: POST /api/payment/webhook
    API->>API: invoice Paid, session Completed
    API->>ESP: EXIT_APPROVED queued
    ESP->>ESP: Open exit servo
```

**Development:** `POST /api/payment/verify` simulates a successful payment without a bank (`ABA_PAY_USE_MOCK=true` default).

---

## Firmware (ESP32 / PlatformIO)

Source: **`iot/`** — Arduino C++, one binary per role (`-e entry_gate` / `-e exit_gate`).

| Module | Purpose |
|--------|---------|
| `src/main.cpp` | app orchestration: sensors, RFID, backend calls, LCD/LEDs, command ack |
| `src/rfid_reader.*` | RC522 on remapped SPI with duplicate-read suppression |
| `src/gate_hardware.*` | servo, LEDs, cached 16x2 LCD writes |
| `src/ultrasonic_sensor.*` | reusable HC-SR04 driver (approach + passage) |
| `src/wifi_manager.*` | non-blocking Wi-Fi connect + retry backoff |
| `src/api_client.*` | authenticated HTTP (device code/token), JSON via ArduinoJson |
| `lib/parking_core/` | pure logic: UID handling, scan gate, **fail-safe gate state machine** (host-tested) |
| `test/test_parking_logic/` | 27 Unity unit tests (`pio test -e native`) |

Build / upload / test:

```powershell
cd iot
pio run -e entry_gate          # or: pio run (default = entry)
pio run -e exit_gate
pio run -e entry_gate -t upload --upload-port COM5
pio test -e native             # host unit tests (no ESP32 needed)
```

See [`iot/README.md`](iot/README.md) for wiring, secrets, expected boot logs, fail-safe details and troubleshooting.

---

## Tests

| Suite | Command | Coverage |
|-------|---------|----------|
| Firmware unit tests | `cd iot && pio test -e native` | 27 tests: UID format/normalize, duplicate-scan suppression, entry/exit flows, auth timeout, denial, passage-blocked hold-open, sensor fault, approval latch/expiry, payment-pending, "ultrasonic alone never opens" |
| Backend integration tests | `cd backend && .\.venv\Scripts\python.exe -m pytest` | 34 tests on an isolated DB: card registry/status/duplicates, RFID entry (session, receipt, command, ack), RFID exit (fee, payment gating, positive/negative), command expiry for **disconnected devices**, late acks, device auth, payment/invoice/ABA regression |
| Live end-to-end | API running, then `cd backend` → `python -m scripts.test_integration` | 34 checks against a live server incl. duplicate/unknown/blocked card, gate command queue + acks, ABA QR, CORS |

Backend tests need `pip install -r requirements-dev.txt` (adds pytest). The firmware host tests need a C++ compiler on PATH.

---

## Key API Endpoints

| Method | Path | Caller |
|--------|------|--------|
| `POST` | `/api/rfid/entry-scan` | Entry ESP32 — card tap → session + `ENTRY_APPROVED` |
| `POST` | `/api/rfid/exit-scan` | Exit ESP32 — card tap → fee / paid check |
| `GET` | `/api/iot/commands/next?deviceCode=` | ESP32 polls gate commands |
| `POST` | `/api/iot/commands/ack` | ESP32 acknowledges (completed/failed + detail) |
| `POST` | `/api/iot/gate/event` | ESP32: car passed / gate closed / gate fault |
| `POST` | `/api/iot/heartbeat` | ESP32 keep-alive |
| `GET` | `/api/rfid/cards`, `POST /api/rfid/cards`, `POST /api/rfid/cards/{uid}` | Dashboard: register/block cards |
| `GET` | `/api/rfid/scans`, `/api/rfid/gate-activity` | Dashboard: history + command states |
| `POST` | `/api/gate/entry/process`, `/api/gate/exit/process` | Manual/simulator lanes (plate / verify-hash) |
| `GET` | `/api/iot/session-status?sessionId=` | Exit station / operators |
| `POST` | `/api/iot/open-gate` | Operator open — only for Completed + Paid sessions |
| `POST` | `/api/payment/webhook` | ABA / KHQR gateway |
| `GET` | `/api/payment/active-session`, `/api/payment/aba-qr` | Dashboard |

Device headers: `x-device-code`, `x-device-token`. Webhook: `x-webhook-secret`. Card management: optional `x-rfid-admin-token` (set `RFID_ADMIN_TOKEN`).

---

## Dashboard Routes

| Route | Purpose |
|-------|---------|
| `/` | KPIs, charts, occupancy |
| `/parking` | Session history + filters |
| `/payment` | Fee + ABA KHQR (live-updates via revision polling) |
| `/invoices` | List, preview, print receipts |
| `/rfid` | **RFID cards, scan history, gate command activity** (live-updates) |

Real-time updates use the existing revision-polling pattern: the backend bumps a revision on scans, acks, gate events and payments; `useParkingLiveSync` reloads the affected pages.

---

## Project Structure

```
IOT-Parking/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                 # config, database, bootstrap, migrations, security
│   │   ├── models/               # sessions, invoices, device_commands, iot_devices,
│   │   │                         # device_logs, rfid_cards, rfid_scan_events
│   │   ├── schemas/              # camelCase API schemas
│   │   ├── routers/              # parking, invoices, payment, dashboard, iot, rfid, gate
│   │   └── services/             # parking, invoice, payment, ABA, iot entry/exit,
│   │                             # rfid, gate command/lane/exit-auto, receipt printer
│   ├── devices/                  # optional CLI stations (entry/exit) + shared client
│   ├── scripts/                  # reset_db, seed, test_integration
│   ├── tests/                    # pytest suite (isolated temp DB)
│   ├── docs/IOT_DEVICES.md       # device API + command lifecycle reference
│   └── data/                     # SQLite + receipts (gitignored)
│
├── frontend/
│   └── app/
│       ├── pages/                # /, /parking, /payment, /invoices, /rfid
│       ├── components/           # tables, KHQR card, invoice preview
│       └── composables/          # API clients, live sync, table hooks
│
├── iot/                          # ESP32 firmware (PlatformIO, Arduino C++)
│   ├── platformio.ini            # envs: esp32dev / entry_gate / exit_gate / native
│   ├── include/                  # parking_config.h + parking_secrets(.example).h
│   ├── lib/parking_core/         # host-testable logic (UID, scan gate, state machine)
│   ├── src/                      # main + hardware/service modules
│   └── test/test_parking_logic/  # Unity unit tests
│
├── scripts/run_backend.ps1
└── README.md
```

### Database tables

| Table | Purpose |
|-------|---------|
| `parking_sessions` | Visit while the vehicle is inside (`Active` → `Completed`) |
| `invoices` | Ticket; `exit_verify_hash` for the barcode |
| `device_commands` | Gate commands (`pending → delivered → acked/failed/expired`) with `expires_at` |
| `iot_devices` / `device_logs` | Device registry + IoT audit trail |
| `rfid_cards` | Registered RFID cards → plate, type, label, status |
| `rfid_scan_events` | Every card presentation (accepted + rejected) |
| `payment_transactions` / `bank_settings` | Payment audit + bank info |

---

## Environment Files

| File | Purpose |
|------|---------|
| `backend/.env.example` | API, SQLite, RFID cooldown/admin token, command timeout, IoT tokens, ABA Pay |
| `frontend/.env.example` | `NUXT_PUBLIC_API_URL`, site URL |
| `iot/include/parking_secrets.example.h` | Wi-Fi, API base URL, device tokens (copy to `parking_secrets.h`) |

Do not commit `.env` or `iot/include/parking_secrets.h` (both gitignored).

**PostgreSQL:** the backend is SQLAlchemy-based; switch by installing
`psycopg2-binary` and setting `DATABASE_URL=postgresql+psycopg2://user:pass@host/db`.
SQLite remains the default for local demos.

---

## Security notes

- **RFID UID ≠ authentication.** MIFARE Classic UIDs can be read and cloned
  with cheap hardware. This project treats the card as an identifier for a
  local demo; a production parking system needs a second factor (staff gate,
  PIN entry, secure-element/diversified-key cards, or license-plate
  cross-check).
- Device tokens default to `secret-*-token` — replace them in `backend/.env`
  **and** `iot/include/parking_secrets.h` for anything beyond local demos.
- Set `RFID_ADMIN_TOKEN` in production so card registration/blocking requires
  the `x-rfid-admin-token` header.
- Gate approvals expire (180 s): a stale "open gate" command can never execute
  later, and disconnected gates surface as `expired` in gate activity.
- The passage safety sensor is fail-safe: blocked or faulty ⇒ gate holds open
  and reports `gate_fault` instead of closing on a vehicle.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| ESP32 LCD `WiFi offline` | wrong SSID/password in `parking_secrets.h`, or out of range |
| ESP32 LCD `RFID reader error` | RC522 wiring / 3.3 V; SS 4, SCK 14, MOSI 23, MISO 19, RST 27 |
| Scan denied "Card not registered" | register the UID on the dashboard `/rfid` page |
| Exit stays locked with fee shown | complete payment (KHQR webhook / Payment page / `exit/mock-payment`) |
| Gate never opens after scan | API unreachable from the gate (LAN IP + firewall), or token mismatch with `backend/.env` |
| `FAILSAFE open` on LCD | passage sensor blocked/faulty — clear the passage; gate closes when safe |
| Commands stuck `pending` then `expired` | gate did not poll (offline) — check power/Wi-Fi; approvals expire by design |
| Port 8000 blocked | allow it in Windows Firewall or free the port |

---

## Reset / seed data

```powershell
cd backend
python scripts/reset_db.py          # wipe + recreate (dev only)
python scripts/reset_db.py --demo   # + sample sessions
```

---

## Push to GitHub

```powershell
git add .
git status
git commit -m "Smart IoT Parking: RFID gates, backend integration, dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```
