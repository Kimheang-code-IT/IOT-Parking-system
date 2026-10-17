# Smart IoT Parking — Docker Infrastructure

Local production-style deployment of the existing Smart IoT Parking System:
**Nuxt dashboard + FastAPI backend + PostgreSQL**, fronted by **nginx**, with
the **ESP32 RFID gates** (`iot/`) connecting to the backend over your LAN/Wi-Fi.

Nothing about the application logic, database schema or firmware changes by
running this stack — it packages what already exists in `backend/`, `frontend/`
and serves it on one HTTP entry point.

```
Browser / ESP32 ──HTTP──▶ nginx :${HTTP_PORT}
                            ├── /            → frontend (Nuxt SSR)      :3000
                            ├── /api/        → backend  (FastAPI)       :8000
                            ├── /docs|/redoc|/openapi.json → FastAPI docs
                            └── /health      → FastAPI health
                                  backend ──▶ db (PostgreSQL) :5432   [private network]
```

| Service | Image / build | Published port | Networks |
|---------|---------------|----------------|----------|
| `nginx` | `nginx:1.29-alpine` | **`${HTTP_PORT}` → 80** | app-net |
| `frontend` | `infrastructure/docker/frontend.Dockerfile` (node:22-alpine, multi-stage) | none (internal :3000) | app-net |
| `backend` | `infrastructure/docker/backend.Dockerfile` (python:3.12-slim) | none (internal :8000) | app-net, db-net |
| `db` | `postgres:17-alpine` | none — private network only | db-net (internal) |
| `migrate` | one-off profile service | — | db-net |

- PostgreSQL data → named volume `postgres_data` (survives restarts/recreation).
- Generated parking receipts → named volume `receipts_data` (mounted at
  `/app/data/receipts` in the backend).
- `migrate` never runs automatically in parallel; it is an explicit one-off
  step (started by `start.ps1` before the API).

---

## Requirements

- **Windows 10/11** with **Docker Desktop** (WSL2 backend recommended),
  Compose v2 (bundled) — `docker compose version` must work.
- 4 GB+ free RAM for the stack (PostgreSQL + Nuxt SSR + FastAPI).
- The repository at `D:\IOT-Parking` (paths below assume this).
- Optional: an ESP32 gate on the same LAN for hardware testing.
- Ports: `${HTTP_PORT}` (default **80**) free on the Docker host.

Docker Desktop prerequisites: virtualization enabled (WSL2), Docker Desktop
started and the whale icon shown as running.

## Project structure (infrastructure/)

```text
infrastructure/
├── compose.yaml            # db + backend + migrate + frontend + nginx
├── .env.example            # copy to .env and fill in
├── .gitignore              # keeps .env + backups/ out of git
├── docker/
│   ├── backend.Dockerfile  # FastAPI, non-root, uvicorn production server
│   └── frontend.Dockerfile # pnpm install → nuxt build → Nitro runtime
├── nginx/
│   └── nginx.conf          # routing, WebSocket upgrade, timeouts, headers
├── scripts/
│   ├── start.ps1           # checks → build → db → migrate → up → URLs
│   ├── stop.ps1            # stop (volumes preserved)
│   ├── restart.ps1         # restart services + status
│   ├── backup-db.ps1       # timestamped pg_dump to infrastructure/backups
│   └── restore-db.ps1      # validated restore with confirmation
└── README.md               # this file
```

## Environment setup

```powershell
cd D:\IOT-Parking\infrastructure
Copy-Item .env.example .env
notepad .env
```

Required edits in `.env`:

| Key | What to set |
|-----|-------------|
| `POSTGRES_PASSWORD` | a strong password (URL-safe: letters/digits) |
| `DATABASE_URL` | keep in sync with the password (hostname `db` is correct for Docker) |
| `PAYMENT_WEBHOOK_SECRET` | strong random string (ABA webhook signature) |
| `RFID_ADMIN_TOKEN` | strong random string (guards card management APIs) |
| `IOT_ENTRY_DEVICE_TOKEN` / `IOT_EXIT_DEVICE_TOKEN` | must match `iot/include/parking_secrets.h` |
| `API_BASE_URL`, `ABA_PAY_CALLBACK_URL`, `NUXT_PUBLIC_SITE_URL` | your Docker host LAN IP (see „Finding the local LAN IP") |
| `ABA_PAY_USE_MOCK` | `false` for real deployments; `true` only for demos |

Generate secrets in PowerShell:

```powershell
-join ((48..57) + (97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
```

`.env` is git-ignored — never commit it.

## Starting the system

```powershell
cd D:\IOT-Parking\infrastructure
.\scripts\start.ps1
```

What it does: checks Docker → validates `.env` → builds images → starts
PostgreSQL and waits for health → runs the **migration service** → starts
backend/frontend/nginx → waits for health → prints URLs.

First run takes a few minutes (image builds). Later runs are fast:

```powershell
.\scripts\start.ps1 -NoBuild                 # after config/data changes only
.\scripts\start.ps1 -NoBuild -SkipMigrate    # skip the migration step
```

Raw Compose equivalent:

```powershell
docker compose up -d db                                  # database first
docker compose --profile migrate run --rm migrate        # schema + seed rows
docker compose up -d                                     # everything
```

## Stopping / restarting

```powershell
.\scripts\stop.ps1                  # down; volumes (data) preserved
.\scripts\stop.ps1 -KeepContainers  # stop only, keep containers for inspection
.\scripts\restart.ps1               # restart all services
.\scripts\restart.ps1 backend       # restart one service
```

`stop.ps1` never removes volumes — `docker compose down -v` is intentionally
not used anywhere. Database and receipts survive stops, restarts and image
rebuilds.

## Rebuilding images (after updating the app)

```powershell
cd D:\IOT-Parking\infrastructure
docker compose build frontend backend    # or: docker compose build
docker compose up -d
.\scripts\start.ps1 -NoBuild             # alternative: rebuild + migrate + up
```

Backend `requirements.txt` or frontend `pnpm-lock.yaml` changes automatically
invalidate the dependency layer. `backend/` and `frontend/` sources are copied
at build time — rebuild after code changes.

## Applying database migrations

```powershell
docker compose --profile migrate run --rm migrate
```

The migrate service (`python -m scripts.run_migrations`):

1. Fresh PostgreSQL → `alembic upgrade head` (creates the schema from the
   baseline revision in `backend/alembic/versions/`).
2. Database previously created by the app's `create_all` → `alembic stamp head`
   (identical schema; no destructive change).
3. Alembic-managed database → `alembic upgrade head`.
4. Then seeds baseline rows (IoT devices, bank settings) if missing.

It is idempotent and safe to run any time. The API also self-heals missing
tables at startup, so a forgotten migration step cannot break the stack.

**Migrating your existing SQLite data** (one-way, additive, SQLite file is
never modified):

```powershell
cd D:\IOT-Parking\infrastructure

# 1. dry run first — prints what would be copied
docker compose run --rm -v "D:\IOT-Parking\backend\data:/sqlite:ro" backend `
  python -m scripts.migrate_sqlite_to_postgres --sqlite /sqlite/iot_parking.db --dry-run

# 2. real copy + automatic validation (row counts, PKs, paid totals)
docker compose run --rm -v "D:\IOT-Parking\backend\data:/sqlite:ro" backend `
  python -m scripts.migrate_sqlite_to_postgres --sqlite /sqlite/iot_parking.db
```

The script validates row counts, primary keys, the paid-invoice total and the
active-session count, advances PostgreSQL sequences and prints a comparison.
Rollback = keep using the SQLite file (unchanged) by pointing a non-Docker
backend at it; nothing is deleted from SQLite.

## Viewing logs

```powershell
docker compose logs -f               # all services
docker compose logs -f backend       # FastAPI
docker compose logs -f nginx         # proxy access/error log
docker compose logs -f db            # PostgreSQL
docker compose ps                    # status + health
```

Logs are capped (10 MB × 3 files per service) and credentials are masked —
the backend startup line shows `db=postgresql+psycopg2://user:***@db:5432/db`.

## Accessing the application

After `start.ps1` prints the URLs:

| URL | What |
|-----|------|
| `http://localhost/` | Dashboard (or `http://localhost:8080/` if `HTTP_PORT=8080`) |
| `http://localhost/docs` | Swagger UI (development policy — see Security) |
| `http://localhost/health` | API health JSON |
| `http://<LAN-IP>/` | Dashboard from any device on the same network |

## Finding the local LAN IP (for ESP32 and other device access)

```powershell
ipconfig
# or:
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object IPAddress, InterfaceAlias
```

Use the IPv4 address of the adapter connected to the same network as the
ESP32s (usually Wi-Fi or Ethernet). Example: `172.16.112.21`.

## Configuring ESP32 API connectivity

The firmware in `iot/` is **not** containerized; it talks to this stack over
Wi-Fi/LAN through nginx:

1. Flash the gates as usual (`pio run -e entry_gate -t upload`, `-e exit_gate`).
2. Edit `iot/include/parking_secrets.h`:

   ```cpp
   #define PARKING_WIFI_SSID   "YourWiFi"
   #define PARKING_WIFI_PASSWORD "YourPassword"
   // Docker host LAN IP + HTTP_PORT (omit the port when it is 80):
   #define PARKING_API_BASE_URL "http://172.16.112.21"
   #define PARKING_ENTRY_DEVICE_TOKEN "..."   // = IOT_ENTRY_DEVICE_TOKEN from .env
   #define PARKING_EXIT_DEVICE_TOKEN  "..."   // = IOT_EXIT_DEVICE_TOKEN from .env
   ```

3. Rebuild/upload both gate firmwares.
4. Allow inbound TCP `${HTTP_PORT}` on the Windows Firewall (run once as
   Administrator):

   ```powershell
   New-NetFirewallRule -DisplayName "Smart IoT Parking (HTTP)" `
     -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow -Profile Private
   ```

   (Use `-LocalPort 8080` if you changed `HTTP_PORT`.)

5. Verify from a phone/tablet on the same Wi-Fi: open
   `http://<LAN-IP>/api/dashboard/revision` — it must return `{"revision": ...}`.

The ESP32 uses the same endpoints as before (`/api/rfid/entry-scan`,
`/api/rfid/exit-scan`, `/api/iot/commands/next`, …) through nginx; do not use
`localhost` or Docker service names inside firmware. Device authentication
(`x-device-code` / `x-device-token`) and the RFID authorization logic in
FastAPI are unchanged.

## Database backup and restore

```powershell
# backup (custom-format pg_dump, validated, timestamped)
.\scripts\backup-db.ps1
.\scripts\backup-db.ps1 -OutputDir D:\Backups\iot-parking -KeepDays 14

# list backups
Get-ChildItem .\backups

# restore (asks you to type RESTORE; backend is stopped during restore)
.\scripts\restore-db.ps1 -BackupFile .\backups\iot-parking-20261017-120000.dump
```

- Backups are written **outside** containers (default `infrastructure/backups`,
  git-ignored) and validated with `pg_restore --list` before being accepted.
- Restore replaces current data with the backup content — that is the point —
  and requires explicit confirmation. `-Force` skips the prompt (automation).
- Passwords never appear in command lines or logs.

A manual fallback without the scripts:

```powershell
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/m.dump'
docker compose cp db:/tmp/m.dump .\backups\manual.dump
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `docker info` fails | Start Docker Desktop; wait for the whale icon |
| `start.ps1` aborts with CHANGE_ME message | Fill in `infrastructure/.env` |
| Port already allocated on up | Another app uses `${HTTP_PORT}` — set `HTTP_PORT=8080` in `.env` and restart |
| `db` unhealthy | `docker compose logs db`; check `POSTGRES_PASSWORD` has no URL-breaking characters or update `DATABASE_URL` accordingly |
| backend unhealthy / restarts | `docker compose logs backend`; most often a bad `DATABASE_URL` or missing PostgreSQL |
| nginx returns 502 | backend/frontend not healthy yet — `docker compose ps`, wait, then `docker compose restart nginx` |
| Dashboard loads but API calls fail | Check browser dev-tools: requests must go to `/api/...` (same origin). `NUXT_PUBLIC_API_URL` must be `/` |
| ESP32 gets "connection refused" | Wrong LAN IP/port in `parking_secrets.h`, firewall rule missing, or the PC/ESP32 are on different networks |
| Login/`/docs` unreachable from LAN | Allowed by default (development policy). To lock down: comment the `/docs`, `/redoc`, `/openapi.json` blocks in `nginx/nginx.conf` and `docker compose restart nginx` |
| Changed code not visible | `docker compose build` + `docker compose up -d` (frontend/backend are baked into images) |

## Updating the application

```powershell
cd D:\IOT-Parking
git pull                        # or edit sources
cd infrastructure
docker compose build
docker compose --profile migrate run --rm migrate
docker compose up -d
docker compose ps               # verify healthy
```

## Security considerations

- **Only nginx is published.** PostgreSQL has no host port and lives on an
  `internal` Docker network; backend and frontend are reachable only through
  nginx.
- **No secrets in images or git**: `.env` is git-ignored, `backend/.env` and
  `iot/include/parking_secrets.h` are excluded from build contexts; the
  backend masks the database password in its logs.
- **Non-root containers**: backend runs as `app`, frontend as `node`.
- **Device authentication** stays enforced (`x-device-code`/`x-device-token`);
  RFID card management can be locked with `RFID_ADMIN_TOKEN`
  (`x-rfid-admin-token` header).
- **Gate audit trail**: every gate command, acknowledgement, expiry and gate
  event is stored (`device_commands`, `device_logs`, `rfid_scan_events`) and
  visible on the dashboard `/rfid` page.
- **HTTP vs HTTPS**: HTTP is acceptable on a trusted LAN for class/demo use.
  For anything real, terminate TLS in front (or add certs to nginx), set
  `NUXT_PUBLIC_SITE_URL`/`API_BASE_URL` to `https://…`, and keep the database
  off the public network at all times.
- **Mock payments**: `ABA_PAY_USE_MOCK=false` in `.env.example` (live
  profile). Without merchant credentials the backend falls back to mock QR for
  demos — set real sandbox keys for payment testing. The unauthenticated dev
  helper `POST /api/gate/exit/mock-payment` should be removed/blocked for real
  deployments (documented in `backend/docs/IOT_DEVICES.md`).
- `/docs` and `/openapi.json` are exposed for development convenience; disable
  them in `nginx/nginx.conf` for shared networks.

## Verification checklist (executed on this machine)

Results below come from an actual end-to-end run of this stack (Docker Desktop
29.8.2 / Compose v5.6.0, Windows 11, 2026-10-17):

| # | Check | Result |
|---|-------|--------|
| 1 | `docker compose config` valid | PASS |
| 2 | frontend image builds (`pnpm install` + `nuxt build`) | PASS |
| 3 | backend image builds (`pip install`) | PASS |
| 4-5 | PostgreSQL starts on `postgres:17-alpine`, healthcheck green | PASS |
| 6 | backend connects to PostgreSQL (`/health` = ok, query verified) | PASS |
| 7 | Alembic baseline generated + `alembic check` = no drift + `migrate` service runs | PASS |
| 8-11 | dashboard `/`, `/api/...`, `/docs`, `/openapi.json` through nginx | PASS |
| 12 | LAN access via `http://172.16.112.21/` (host LAN IP) | PASS (loopback via LAN IP; a second physical device was not available) |
| 13 | ESP32 physical reachability | NOT TESTED — no hardware attached this session; checklist above covers it |
| 14 | parking session API: card register → RFID entry → gate command → ack | PASS |
| 15 | payment flow: ABA QR (mock fallback) + webhook → EXIT_APPROVED | PASS |
| 16 | gate authorization enforced (unpaid exit = no command; operator open requires Paid) | PASS |
| 17 | data survives `docker compose down`/`up` + `--force-recreate db backend` | PASS (receipts volume + row counts verified) |
| 18 | backup (`backup-db.ps1`) + restore (`restore-db.ps1`) round-trip | PASS (marker row added after backup was reverted; totals matched) |
| 19 | no credentials in container logs (searched generated password) | PASS (DB URL masked in logs) |
| 20 | no database port published (`5432`, `8000`, `3000` closed on host, only nginx `80`) | PASS |
| 21 | SQLite → PostgreSQL data migration (read-only source) | PASS (121 rows; paid total $9.00 → $9.00; active sessions 2 → 2) |
| 22 | `start.ps1` / `stop.ps1` / `restart.ps1` exit codes + health | PASS |
| 23 | WebSocket upgrade forwarding | PARTIAL — nginx forwards `Upgrade`/`Connection` (verified: the backend received a websocket-scope request through the proxy). The app currently exposes no WebSocket route (it uses HTTP revision polling), so no 101 handshake exists to complete. |
| 24 | Windows Firewall rule for LAN port 80 | NOT EXECUTED — creating it requires an elevated PowerShell (command below). Docker Desktop may already allow published ports. |

Run the same checks after changes with the commands in *Troubleshooting* and
the *Backup and restore* sections.

