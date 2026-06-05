# Smart IoT Parking System — Research Report

**Course:** Basic Electronic  
**Project:** IOT-Parking (monorepo: FastAPI + Nuxt + ESP32/Wokwi)  
**Repository:** `IOT-Parking/`

> **Instructor note:** Section **4 (Results and Discussion)** is also summarized in [`backend/README.md`](../backend/README.md) with test reproduction steps.

---

## 1. Introduction

### 1.1 Background

Urban parking facilities in Cambodia and similar markets still rely heavily on manual ticketing, cash collection, and staff memory to match vehicles with payments. Drivers queue at entry and exit lanes; errors in plate recording or lost tickets cause disputes and revenue loss. At the same time, **Internet of Things (IoT)** devices (microcontrollers, servos, sensors, displays) and **mobile banking** (e.g. ABA KHQR) have become affordable for small and medium parking operators.

This project implements a **Smart IoT Parking System** that connects:

- **Edge layer:** ESP32-based gates (simulated in Wokwi) with servos, LCD, LEDs, and lane buttons  
- **Server layer:** FastAPI backend with SQLite, session/invoice logic, and a command queue for gates  
- **Presentation layer:** Nuxt staff dashboard and payment page with live KHQR display  

Entry uses **license plate recognition** (OpenCV + optional Tesseract on a lane PC). Exit uses **barcode verification** on the printed ticket (`plate|invoice|verifyHash`) plus **ABA payment** before the exit gate opens.

### 1.2 Research Problem

Traditional parking operations suffer from:

1. **Slow entry/exit** — manual writing of plate numbers and ticket handover  
2. **Weak traceability** — no single database linking plate, time-in, invoice, and payment  
3. **Payment friction** — cash-only exit lanes; no integration with national QR payment rails  
4. **Disconnected IoT** — gates and software often designed separately, so business rules live on devices instead of a central API  

**Research problem (statement):**  
*How can a low-cost IoT parking architecture combine automated plate capture at entry, cryptographically verifiable exit tickets, ABA KHQR payment, and ESP32 gate control—while keeping staff dashboards read-only for safety and auditability?*

### 1.3 Research Questions

| ID | Research question |
|----|-------------------|
| **RQ1** | Can a three-tier architecture (ESP32 edge, FastAPI server, Nuxt dashboard) complete entry-to-exit parking without manual gate control from the web UI? |
| **RQ2** | Is barcode payload `IOT-PARKING:plate\|invoice\|hash` sufficient to verify exit identity and link to the correct invoice? |
| **RQ3** | Can ABA KHQR (mock or PayWay sandbox) update invoice status so the exit gate opens only after payment? |
| **RQ4** | Can Wokwi simulation reproduce the same API flows as real lane hardware for teaching and demonstration? |

### 1.4 Proposed Framework

The proposed framework has four layers:

```text
┌─────────────────────────────────────────────────────────────┐
│  Staff dashboard (Nuxt) — read-only for gates; KHQR display │
├─────────────────────────────────────────────────────────────┤
│  Parking API (FastAPI) — sessions, fees, invoices, payments   │
│  Gate services — entry/exit trigger, OCR, receipt print       │
│  IoT command queue — ENTRY_APPROVED / EXIT_APPROVED / DENIED  │
├─────────────────────────────────────────────────────────────┤
│  Lane PC — webcam OCR, barcode scan, thermal receipt          │
├─────────────────────────────────────────────────────────────┤
│  ESP32 (Wokwi/real) — servos, LCD, buttons, poll commands     │
└─────────────────────────────────────────────────────────────┘
```

**Entry path:** Lane button → `POST /api/gate/entry/trigger` → session + invoice + `verifyHash` → receipt → `ENTRY_APPROVED` → servo open → auto-close.  

**Exit path:** Scan barcode → `POST /api/gate/exit/trigger` → fee calculation → payment (ABA/mock) → `EXIT_APPROVED` or `EXIT_DENIED`.

### 1.5 Novelty of the Study

For an undergraduate **Basic Electronic** project, novelty is practical rather than theoretical:

1. **Unified barcode contract** — Code128 ticket encodes plate, invoice ID, and HMAC-derived hash in one scan at exit (no second plate OCR required on exit in the default flow).  
2. **Separation of concerns** — Dashboard never opens gates; only IoT endpoints and lane triggers do, reducing misuse risk.  
3. **Simulator parity** — One MicroPython firmware (`wokwi/parking-gate`) and one API surface for both Wokwi buttons and real ESP32 polling.  
4. **Cambodia payment context** — ABA KHQR on the payment page with webhook confirmation aligned to local mobile banking habits.  
5. **Teachable full stack** — Single laptop demo: SQLite, mock QR, Wokwi gateway, and integration test script.

### 1.6 Contribution of Literature Review

This study contributes to practice by:

- Mapping **IoT smart parking** literature (sensors, LPR, cloud dashboards) onto an implementable student stack  
- Applying **REST + device token** patterns from industrial IoT to gate command polling  
- Connecting **electronic payment (QR)** research to parking exit gating logic  
- Documenting **reproducible** test and deployment steps for instructors  

(See Section 2 for theories and prior work that support these choices.)

### 1.7 Aim of the Study

**Aim:** To design, implement, and evaluate an integrated IoT parking system that automates entry identification, exit verification, digital payment, and gate control, with a staff dashboard for monitoring and reporting.

### 1.8 Objectives of the Study

| # | Objective | Deliverable in repo |
|---|-----------|---------------------|
| O1 | Implement entry plate capture and session creation | `gate_trigger_service.py`, `gate_camera_service.py`, `iot_entry_service.py` |
| O2 | Generate verifiable exit tickets and barcode | `exit_verify_utils.py`, `printer_service.py` / receipts |
| O3 | Integrate exit payment and gate approval | `payment_service.py`, `iot_exit_service.py`, ABA mock/PayWay |
| O4 | Control ESP32 gates via command queue | `gate_command_service.py`, `wokwi/parking-gate/main.py` |
| O5 | Provide staff dashboard and payment UI | `frontend/` (parking, payment, invoices) |
| O6 | Validate end-to-end flows with automated tests | `scripts/test_integration.py`, `scripts/test_wokwi_flow.ps1` |

---

## 2. Related Work

### 2.1 First Theory — Internet of Things (IoT) Layered Architecture

**Theory:** IoT systems are commonly described as a stack of **perception** (sensors/actuators), **network** (Wi-Fi/gateway), **processing** (edge or cloud), and **application** (UI/analytics) layers (Gubbi et al., 2013; Azure IoT reference models).

**Relevance:** Entry/exit servos and buttons are perception/actuation; Wokwi gateway and Wi-Fi connect the ESP32 to the host API; FastAPI is processing; Nuxt is application. This project deliberately keeps **gate decisions** in the processing layer, not on the dashboard.

### 2.2 Second Theory — Publish/Subscribe and Command Polling for Constrained Devices

**Theory:** Microcontrollers with intermittent connectivity often use **message queues** or **HTTP long-poll** rather than persistent WebSockets (MQTT is widespread in IoT literature; HTTP polling is simpler for classroom labs).

**Relevance:** ESP32 firmware polls `GET /api/iot/commands/next?deviceCode=` and acknowledges with `POST /api/iot/commands/ack`. Commands are stored in SQLite (`device_commands` table) until delivered—matching industrial “command inbox” patterns at teaching scale.

### 2.3 Third Theory — Optical Character Recognition (OCR) for License Plate Recognition (LPR)

**Theory:** LPR pipelines use **image acquisition → plate localization → character segmentation → OCR** (Anagnostopoulos et al., 2008). Open-source stacks use OpenCV for capture and Tesseract or deep models for text.

**Relevance:** Entry lane uses `GateCameraService` (OpenCV webcam, optional Tesseract). Wokwi substitutes **mock plate** via simulator buttons when no camera exists—same API contract (`source: simulator` vs `camera`).

### 2.4 First Existing Research — Smart Parking with IoT Sensors and Cloud Backend

**Prior work:** Numerous smart-parking papers propose occupancy sensors, mobile apps, and cloud billing (e.g. sensor networks in lots, guidance to free bays).

**Comparison:** This project focuses on **gated lane** control (servos) and **invoice-linked payment**, not only bay occupancy. It is closer to **barrier parking** than street-side slot detection.

### 2.5 Second Existing Research — QR Code Payments in Transport and Parking

**Prior work:** QR-based mobile payments (EMVCo QR, domestic schemes such as KHQR) reduce cash handling; parking systems in Asia increasingly expose QR on exit kiosks or apps.

**Comparison:** The payment page calls `GET /api/payment/aba-qr` and listens for webhook confirmation. Mock mode supports demos without merchant keys; PayWay sandbox is configurable in `.env`.

### 2.6 Third Existing Research — Wokwi and Digital Twin for Embedded Education

**Prior work:** Simulation environments lower cost for ESP32 labs (no physical parts required for every student).

**Comparison:** `wokwi/parking-gate` mirrors production firmware structure (MicroPython, I2C LCD, servos). `wokwigw` bridges the simulator to `host.wokwi.internal:8000` for real API calls during demos.

### 2.7 Research Gap

| Gap in prior practice | How this project addresses it |
|------------------------|-------------------------------|
| Gate UI mixed with payment UI | Dashboard is monitoring-only; gates driven by IoT API |
| Exit relies only on plate re-scan | Barcode binds plate + invoice + HMAC hash |
| IoT and web built as separate assignments | Single repo, one integration test suite |
| No local payment rail in student projects | ABA KHQR + webhook + sandbox mock |
| Hard to demo without hardware | Wokwi + `test_integration.py` on one laptop |

**Remaining gaps (future work):** production PostgreSQL, JWT for staff, real ESC/POS printer, cloud LPR accuracy studies, multi-lane scale-out.

---

## 4. Results and Discussion

*(Full test tables and reproduction commands are in [`backend/README.md`](../backend/README.md).)*

### 4.1 Implementation Results

The system was implemented as specified in Section 1.4. Major components:

| Component | Status | Evidence |
|-----------|--------|----------|
| Entry trigger + session/invoice | Implemented | `POST /api/gate/entry/trigger` |
| Receipt with Code128 barcode | Implemented | `backend/data/receipts/`, `exit_verify_utils.py` |
| Exit trigger + barcode parse | Implemented | `POST /api/gate/exit/trigger` |
| Fee rules (<1h → $1 min; else hourly × $2) | Implemented | `ParkingFeeService`, `.env` rates |
| ABA QR + webhook | Implemented (mock default) | `payment_service.py`, `aba_pay_service.py` |
| ESP32 command queue | Implemented | `iot` router + Wokwi `main.py` |
| Dashboard + payment UI | Implemented | Nuxt `parking.vue`, `payment.vue` |

### 4.2 Functional Test Results (Integration)

Automated test: `python -m scripts.test_integration` (API on `http://127.0.0.1:8000`).

| Test area | Checks | Expected outcome |
|-----------|--------|------------------|
| API health | 1 | `status: ok` |
| Dashboard analytics | 5 | JSON charts/stats |
| Parking & invoices lists | 2 | Paginated `data` |
| Bank info | 1 | Bank name present |
| Gate entry trigger | 2 | `success`, receipt path |
| Legacy IoT entry | 1 | Compatible or 409 on duplicate |
| Verify hash on ticket | 1 | Non-empty hash |
| Payment active session + QR | 2 | Plate match, `data:image` QR |
| Parking DB entry | 1 | Row searchable by plate |
| Gate exit + legacy exit | 2 | Fee calculated, success |
| Webhook + session status | 2 | Paid, `canOpenGate` |
| Open exit gate + invoice Paid | 2 | Command success, DB status |
| Device poll + CORS | 2 | 200/204, localhost allowed |

**Target:** 24/24 checks pass when the backend is running with default `.env` from `.env.example`.

### 4.3 Fee Calculation (Sample)

| Duration parked | Rule | Example fee (USD) |
|-----------------|------|-------------------|
| &lt; 1 hour | Minimum fee | $1.00 |
| 1 hour | ceil(1) × $2/h | $2.00 |
| 2 h 10 min | ceil(2.17) × $2/h | $6.00 |

Configured via `MINIMUM_FEE=1.00` and `RATE_PER_HOUR=2.00`.

### 4.4 Wokwi Demonstration Results

With API + `wokwigw.exe` + simulation running:

| Step | Observation |
|------|-------------|
| Upload firmware | Serial: `boot.py: MicroPython starting` → `Booting...` → LCD test |
| API online | LCD shows connectivity when backend reachable |
| Green button (entry) | Entry servo opens; receipt saved; session Active |
| Blue button (exit) | Barcode flow; mock payment (if enabled); exit servo opens |
| Denied exit | Unpaid or bad barcode → `EXIT_DENIED`, red LED + buzzer (sim) |

### 4.5 Discussion

**RQ1 (three-tier architecture):** Integration tests show the API coordinates database, payment, and IoT commands without dashboard gate control—supporting the architectural objective.

**RQ2 (barcode verification):** Encoding `IOT-PARKING:plate|invoice|hash` allows exit to resolve the invoice in one scan; HMAC hash reduces forgery compared to plate-only tickets.

**RQ3 (ABA payment):** Mock QR and webhook path demonstrate exit gating after `Paid` status; production PayWay keys remain optional.

**RQ4 (Wokwi parity):** Simulator uses the same REST triggers as lane scripts; students can demo without physical ESP32, then deploy the same `main.py` to hardware.

**Limitations:** OCR accuracy depends on camera and lighting; SQLite is single-user; device tokens in `.env` are not rotated; exit plate OCR is optional and barcode-first by design.

### 4.6 Conclusion

The Smart IoT Parking System meets its stated objectives: automated entry, verifiable tickets, digital payment integration, IoT gate commands, and staff visibility. Results are reproducible via documented scripts and suitable for classroom demonstration and instructor review.

---

## References (indicative)

- Anagnostopoulos, C.-N., et al. (2008). License plate recognition—A brief tutorial. *IEEE Intelligent Transportation Systems Magazine*.  
- Gubbi, J., et al. (2013). Internet of Things (IoT): A vision, architectural elements, and future directions. *Future Generation Computer Systems*.  
- EMVCo (2023). QR Code Specifications for Payment Systems.  
- Wokwi Documentation — ESP32 simulation and IoT Gateway.  
- ABA PayWay Developer Documentation (sandbox checkout).

*Add your course-required citation style (APA/IEEE) when submitting.*
