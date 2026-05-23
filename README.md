# IOT Parking System (development)

| Folder | Role |
|--------|------|
| `backend/` | FastAPI API — **SQLite** |
| `frontend/` | Nuxt dashboard |
| `wokwi/` | ESP32 simulator (entry / exit gates) |
| `docs/` | **[SYSTEM_DOCUMENTATION.md](docs/SYSTEM_DOCUMENTATION.md)** — full guide |
| `index.html` | **13-slide presentation** (browser, ← → keys, F11 fullscreen) |

## Quick start

```powershell
# API
cd backend
pip install -r requirements.txt
copy .env.example .env
.\scripts\run_dev.ps1

# UI (new terminal)
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:3000 — API docs: http://127.0.0.1:8000/docs

## Documentation (one file)

**[docs/SYSTEM_DOCUMENTATION.md](docs/SYSTEM_DOCUMENTATION.md)** — architecture, database, IoT flows, API, demo script, testing, and **suggested 20-slide outline** for university presentation.

```powershell
cd backend
python -m scripts.test_integration
```

## IoT

- Wokwi: `wokwi/entry-gate`, `wokwi/exit-gate`
- Python: `backend/devices/entry_station.py`, `exit_station.py`

## Environment files

| File | Purpose |
|------|---------|
| `backend/.env.example` | Copy to `backend/.env` (API, SQLite, IoT tokens) |
| `frontend/.env.example` | Copy to `frontend/.env` (API URL, site URL for SEO) |
| `backend/devices/.env.example` | Optional — lane PC device credentials |

**Never commit** `.env` files or `backend/data/*.db` — they are in `.gitignore`.

## Push to GitHub

### 1. Create an empty repository on GitHub

Do not add a README, `.gitignore`, or license on GitHub (this repo already has them).

### 2. First push from your machine

```powershell
cd D:\IOT-Parking

git init
git add .
git status
# Confirm .env and backend/data/ are NOT listed

git commit -m "Initial commit: IOT Parking System"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPO` with your GitHub details.

### 3. After clone (for you or teammates)

```powershell
cd backend
copy .env.example .env
pip install -r requirements.txt
python scripts/reset_db.py

cd ..\frontend
copy .env.example .env
pnpm install
pnpm dev
```

### Reset test data

```powershell
cd backend
python scripts/reset_db.py
```
