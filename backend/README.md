# IOT Parking — API (development)

FastAPI + SQLite for the Nuxt dashboard and Wokwi / lane scripts.

**Full system documentation:** [../README.md](../README.md)

## Setup

```powershell
pip install -r requirements.txt
copy .env.example .env
.\scripts\run_dev.ps1
```

Or: `python -m scripts.seed` then `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

- OpenAPI: http://127.0.0.1:8000/docs
- Database: `data/iot_parking.db`

### Clear all test data

Stop the API server, then:

```powershell
python scripts/reset_db.py
```

This deletes `data/iot_parking.db` and recreates empty tables (IoT devices + bank settings only). Add sample rows again with `python scripts/reset_db.py --demo` or `python -m scripts.seed`.

## Tests

```powershell
python -m scripts.test_integration
```

## IoT

See [docs/IOT_DEVICES.md](docs/IOT_DEVICES.md) for device headers. Overview and flows: [../README.md](../README.md).
