# IOT Parking System

Smart parking management platform — IoT entry/exit lanes, barcode ticket verification, KHQR payment, and a staff web dashboard.

---

## Overview

The **IOT Parking System** automates parking operations from vehicle entry to exit payment. When a car enters, an IoT device records the license plate, creates a parking session and invoice, and prints a thermal receipt with a **barcode** for exit verification. At exit, the lane scans the barcode and confirms the plate, the backend calculates the fee, the customer pays via **ABA Pay / KHQR**, and the gate opens after payment is confirmed.

The system is split into three layers:

| Layer | Role | Users |
|-------|------|--------|
| **Edge (IoT)** | Cameras, printers, barcode scanners, gate relays, ESP32 simulators | Drivers (indirect), lane hardware |
| **Server** | FastAPI REST API, business logic, SQLite database | All clients over HTTP |
| **Web dashboard** | Real-time stats, parking history, payment display, invoices | Parking staff / admin |

**Design rule:** The web dashboard does **not** control gates or printers. Only registered IoT devices call `/api/iot/*`. Staff use reporting APIs and the payment display page for KHQR.

**Fee rules:** Under 1 hour → minimum $1.00. One hour or more → billed hours (rounded up) × $2.00/hour.

---

## Technology Stack

| Category | Technology | Version / Notes | Purpose |
|----------|------------|-----------------|---------|
| **Backend language** | Python | 3.11+ | API server and IoT lane scripts |
| **API framework** | FastAPI | ≥ 0.115 | REST API, OpenAPI docs at `/docs` |
| **ASGI server** | Uvicorn | ≥ 0.32 | Development and production server |
| **ORM** | SQLAlchemy | 2.x | Database models and queries |
| **Migrations** | Alembic | ≥ 1.14 | Schema migrations (optional) |
| **Validation** | Pydantic | v2 | Request/response schemas (camelCase JSON) |
| **Database** | SQLite | `backend/data/iot_parking.db` | Local development; single-file DB |
| **Rate limiting** | slowapi | ≥ 0.1.9 | API abuse protection |
| **HTTP client** | httpx | ≥ 0.27 | ABA PayWay sandbox calls |
| **QR generation** | qrcode + Pillow | ≥ 7.4 | Mock ABA KHQR images |
| **Barcode** | python-barcode | ≥ 0.15 | Code128 exit verification on printed ticket |
| **Frontend framework** | Nuxt | 4.x | Staff dashboard SPA |
| **UI library** | Vue | 3.5+ | Reactive UI |
| **Language** | TypeScript | 5.9+ | Type-safe frontend code |
| **Component library** | Nuxt UI | 4.x | Tables, forms, layout, badges |
| **Styling** | Tailwind CSS | 4.x | Utility-first CSS |
| **Charts** | ECharts + vue-echarts | 6.x / 8.x | Dashboard analytics |
| **Tables** | TanStack Vue Table | 8.x | Sortable, filterable data grids |
| **State / data** | Pinia, Vue Query | — | Client state and API caching |
| **i18n** | @nuxtjs/i18n | 10.x | English UI |
| **Package manager** | pnpm | 10.x | Frontend dependencies |
| **IoT simulation** | Wokwi + ESP32 (C++) | — | Entry/exit gate HTTP demo |
| **IoT scripts** | Python | `backend/devices/` | Lane clients without physical hardware |

---

## Project Structure

```
IOT-Parking/
├── backend/                      # FastAPI API server
│   ├── app/
│   │   ├── main.py               # App entry, CORS, routers, health
│   │   ├── core/                 # Config, database, bootstrap, security
│   │   ├── models/               # SQLAlchemy tables (sessions, invoices, devices…)
│   │   ├── schemas/              # Pydantic request/response DTOs
│   │   ├── routers/              # HTTP routes (parking, payment, iot…)
│   │   ├── services/             # Business logic layer
│   │   └── utils/                # Dates, IDs, barcode, QR helpers
│   ├── devices/                  # Entry/exit lane Python clients
│   │   ├── entry_station.py      # Entry: scan → print ticket → gate
│   │   ├── exit_station.py       # Exit: barcode → pay → open gate
│   │   └── client.py             # Shared HTTP client for IoT API
│   ├── scripts/
│   │   ├── reset_db.py           # Wipe test data
│   │   ├── seed.py               # Optional demo sessions
│   │   └── test_integration.py   # End-to-end API test
│   ├── docs/IOT_DEVICES.md       # IoT integration guide
│   ├── data/                     # SQLite DB (gitignored, created on first run)
│   ├── .env.example              # Environment template
│   └── requirements.txt
│
├── frontend/                     # Nuxt 4 staff dashboard
│   ├── app/
│   │   ├── pages/                # index, parking, payment, invoices
│   │   ├── components/           # Tables, KHQR card, invoice preview
│   │   ├── composables/          # API hooks and table logic
│   │   ├── layouts/              # Dashboard shell + sidebar
│   │   └── assets/               # CSS, images (logo)
│   ├── public/                   # favicon, static files
│   ├── nuxt.config.ts
│   └── .env.example
│
├── wokwi/                        # ESP32 simulators (Wokwi)
│   ├── entry-gate/               # Simulated entry button → entry-scan
│   └── exit-gate/                # Simulated exit scan → exit-verify
│
├── docs/
│   └── SYSTEM_DOCUMENTATION.md   # Extended technical documentation
│
├── index.html                    # Presentation slides (browser)
├── README.md                     # This file
└── .gitignore
```

### Key modules (backend services)

| Module | Responsibility |
|--------|----------------|
| `ParkingService` | Create, list, and close parking sessions |
| `ParkingFeeService` | Time-based fee calculation |
| `InvoiceService` | Pending/paid invoices linked to sessions |
| `PrinterService` | Receipt `printData` for entry thermal printer |
| `IotEntryService` | Entry scan → session + invoice + barcode ticket |
| `IotExitService` | Exit verify (barcode + plate), gate control |
| `PaymentService` | Active session, payment verify, bank webhook |
| `AbaPayService` | ABA PayWay / mock KHQR QR generation |
| `DashboardService` | Stats, occupancy, charts for home page |

### Dashboard pages

| Route | Purpose |
|-------|---------|
| `/` | KPIs, occupancy trend, vehicle types, peak hours |
| `/parking` | Parking history with filters |
| `/payment` | Active vehicle fee + ABA KHQR display (no receipt UI) |
| `/invoices` | Invoice list, preview, and thermal print |

---

## Whole Project Flow

End-to-end lifecycle from entry to exit:

```mermaid
flowchart TB
    subgraph Entry["1 — Entry lane"]
        A1[Vehicle arrives] --> A2[Camera / LPR detects plate]
        A2 --> A3[POST /api/iot/entry-scan]
        A3 --> A4[Create Active session + Pending invoice]
        A4 --> A5[Print receipt with barcode verifyHash]
        A5 --> A6[Optional: open entry gate]
    end

    subgraph Parking["2 — While parked"]
        B1[Session status: Active]
        B2[Staff dashboard shows occupancy and history]
        B1 --- B2
    end

    subgraph Exit["3 — Exit lane"]
        C1[Driver presents printed ticket] --> C2[Scan barcode + read plate]
        C2 --> C3[POST /api/iot/exit-verify]
        C3 --> C4[Calculate parking fee]
        C4 --> C5{Payment status?}
        C5 -->|Pending| C6[Show KHQR / payment terminal]
        C6 --> C7[POST /api/payment/webhook]
        C7 --> C8[Poll GET /api/iot/session-status]
        C5 -->|Paid| C9[POST /api/iot/open-gate]
        C8 -->|canOpenGate| C9
        C9 --> C10[Session Completed · Invoice Paid]
    end

    subgraph Web["Staff dashboard (parallel)"]
        W1[Home — analytics]
        W2[Parking — history]
        W3[Payment — KHQR display]
        W4[Invoices — records and reprint]
    end

    A6 --> Parking
    Parking --> Exit
    Parking -.-> Web
    C6 -.-> W3
```

---

## Entry Flow

When a vehicle enters the parking lot:

```mermaid
sequenceDiagram
    autonumber
    participant Driver
    participant Cam as Camera / LPR
    participant Dev as Entry device
    participant API as FastAPI
    participant DB as SQLite
    participant Prt as Thermal printer

    Driver->>Cam: Vehicle arrives at entry
    Cam->>Dev: License plate + vehicle type
    Dev->>API: POST /api/iot/entry-scan
    Note over Dev,API: Headers: x-device-code, x-device-token

    API->>DB: Insert parking_sessions Active
    API->>DB: Insert invoices Pending + exit_verify_hash
    API-->>Dev: sessionId, invoiceId, printData

    Dev->>Prt: Print receipt with barcode
    Dev->>Driver: Optional open entry gate
    Driver->>Driver: Keep printed ticket for exit
```

**Printed ticket includes:** invoice number, plate, vehicle type, entry date/time, **Code128 barcode** (`verifyHash`).

---

## Exit Flow

When a vehicle leaves the parking lot:

```mermaid
sequenceDiagram
    autonumber
    participant Driver
    participant Scan as Barcode scanner
    participant Cam as Exit camera
    participant Dev as Exit device
    participant API as FastAPI
    participant DB as SQLite
    participant Gate as Gate relay

    Driver->>Scan: Present printed ticket
    Scan->>Dev: verifyHash from barcode
    Cam->>Dev: License plate from LPR
    Dev->>API: POST /api/iot/exit-verify
    Note over Dev,API: Body: verifyHash + licensePlate

    API->>DB: Lookup invoice by verifyHash
    API->>API: Match plate and calculate fee
    API-->>Dev: sessionId, invoiceId, amount, paymentStatus

    alt Payment still Pending
        Dev->>Dev: Trigger payment terminal or kiosk
        loop Poll until paid
            Dev->>API: GET /api/iot/session-status
        end
    end

    Dev->>API: POST /api/iot/open-gate
    API->>DB: Session Completed, Invoice Paid
    Dev->>Gate: Open exit barrier
    Gate->>Driver: Vehicle exits
```

---

## Payment Flow

Payment happens at exit (IoT terminal or staff kiosk). The **Payment** page shows the fee and ABA KHQR for the active session — invoices are printed at entry only.

```mermaid
sequenceDiagram
    autonumber
    participant Customer
    participant Kiosk as Payment kiosk or dashboard
    participant Terminal as ABA Mobile or bank
    participant API as FastAPI
    participant DB as SQLite
    participant Exit as Exit lane device

    Note over Exit,API: Exit-verify already ran — fee is known

    Kiosk->>API: GET /api/payment/active-session
    API->>DB: Find Active session and pending invoice
    API-->>Kiosk: plate, entryTime, duration, amount

    Kiosk->>API: GET /api/payment/aba-qr
    API-->>Kiosk: KHQR image mock or PayWay sandbox

    Kiosk->>Customer: Display amount and QR
    Customer->>Terminal: Scan KHQR with ABA app
    Terminal->>API: POST /api/payment/webhook
    Note over Terminal,API: Header x-webhook-secret

    API->>DB: Mark invoice Paid, close session
    API-->>Terminal: OK

    Exit->>API: GET /api/iot/session-status
    API-->>Exit: canOpenGate true
    Exit->>API: POST /api/iot/open-gate
    Exit->>Customer: Gate opens
```

**Alternative (development):** `POST /api/payment/verify` with plate and amount simulates a successful payment.

---

## Conclusions

This project demonstrates a complete **IoT + web** parking solution suitable for university presentation and local development:

1. **Separation of concerns** — IoT devices handle lanes; the dashboard is for monitoring, payment display, and billing records only.
2. **Traceability** — Every visit links a parking session, invoice, and payment transaction.
3. **Secure exit verification** — HMAC-based `verifyHash` on a printed barcode, validated with the license plate at exit.
4. **Digital payment ready** — ABA PayWay / KHQR with webhook confirmation before the gate opens.
5. **Demo without full hardware** — Wokwi ESP32 simulators and Python lane scripts use the same API as real devices.

**Current scope (development):** SQLite, mock ABA QR by default, no staff login, device tokens in `.env` for local testing.

**Future work:** PostgreSQL, JWT auth, real ESC/POS printer SDK, live PayWay credentials, multi-lot support.

For API reference, database design, and demo script see **[docs/SYSTEM_DOCUMENTATION.md](docs/SYSTEM_DOCUMENTATION.md)**.

---

## Quick Start

```powershell
# API
cd backend
pip install -r requirements.txt
copy .env.example .env
.\scripts\run_dev.ps1

# UI (new terminal)
cd frontend
copy .env.example .env
pnpm install
pnpm dev
```

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Staff dashboard |
| http://127.0.0.1:8000/docs | API documentation (Swagger) |

```powershell
cd backend
python -m scripts.test_integration
python scripts/reset_db.py
```

---

## Environment Files

| File | Purpose |
|------|---------|
| `backend/.env.example` | Copy to `backend/.env` |
| `frontend/.env.example` | Copy to `frontend/.env` |
| `backend/devices/.env.example` | Optional lane PC credentials |

Never commit `.env` or `backend/data/*.db`.

---

## IoT and Simulation

| Component | Path |
|-----------|------|
| Wokwi entry gate | `wokwi/entry-gate/` |
| Wokwi exit gate | `wokwi/exit-gate/` |
| Entry lane script | `backend/devices/entry_station.py` |
| Exit lane script | `backend/devices/exit_station.py` |

Details: **[backend/docs/IOT_DEVICES.md](backend/docs/IOT_DEVICES.md)**

---

## Push to GitHub

```powershell
cd D:\IOT-Parking
git add .
git status
git commit -m "Initial commit: IOT Parking System"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```
