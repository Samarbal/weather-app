# Stillweather — Weather Forecast App

A simple, clear weather app: search any city or use your device location, then see current
conditions and a 3-hourly forecast for the next five days.

**Delivered with the full SDLC using an AI agent (Native AI) — from product intent to a deployed
app in under 3 hours.**

## What was delivered

| SDLC stage | Artifact |
|---|---|
| Requirements | [`intent/weather-app.md`](intent/weather-app.md) — users, problem, workflow, scope |
| Specification | [`docs/specs/SPEC-001.md`](docs/specs/SPEC-001.md) — functional requirements, API contract, acceptance criteria |
| Planning | [`docs/plans/PLAN-001.md`](docs/plans/PLAN-001.md) — architecture, task breakdown, estimates, risks |
| Implementation | FastAPI backend (`app/`) + React/TypeScript frontend (`frontend/`) |
| Testing | Mocked unit and route tests (`tests/`), no live API quota consumed |
| Review | Test run, secret-leak audit, spec-conformance check |

Timebox: **~3 hours total** (backend MVP estimated at 2 hours; frontend and deployment completed after).

## Features

- City search with debounced autocomplete and full keyboard navigation
- "Use my location" — device geolocation only after an explicit user action, with a clear
  recovery path when permission is denied
- Current conditions: temperature, feels-like, humidity, wind, condition
- 3-hourly forecast points grouped into a 5-day view with expandable days
- Loading, empty, and error states throughout — no blank or frozen screens
- English UI, Celsius temperatures, km/h wind speeds, responsive layout

## Tech stack

- **Backend:** Python 3.11+, FastAPI, Pydantic, HTTPX — Swagger UI at `/docs`
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, lucide-react
- **Weather data:** OpenWeather (Current Weather, Direct Geocoding, 5 Day / 3 Hour Forecast)
- **No database** — the app is a read-only proxy over OpenWeather

## Project structure

```text
app/
  main.py                     FastAPI app, CORS, static frontend hosting, /health
  api/routes/weather.py       The three REST operations; HTTP mapping only
  schemas/weather.py          Pydantic request/response contracts
  services/weather_service.py Use-case logic, unit conversion (m/s → km/h)
  clients/openweather_client.py  HTTPX calls, timeouts, upstream error translation
  core/config.py              Server-side settings and API key loading
frontend/                     React + Vite app (built to frontend/dist)
tests/                        Mocked client, service, and route tests
docs/specs/  docs/plans/      Specification and implementation plan
intent/                      Product intent
```

## Getting started

### 1. Backend

```bash
pip install -r requirements.txt
copy .env.example .env      # then set OPENWEATHER_API_KEY in .env
uvicorn app.main:app --reload
```

- API base: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

`OPENWEATHER_API_KEY` is read only from the server environment (or the ignored `.env` file).
It is never hardcoded, logged, or returned by the API.

### 2. Frontend

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173, proxies /api to 127.0.0.1:8000
npm run build      # outputs to frontend/dist, served by FastAPI at /
```

### 3. Tests

```bash
python -m pytest
```

Tests use a mocked HTTPX transport, so they run offline and consume no OpenWeather quota.

## API

All application routes are under `/api/v1`.

| Method & path | Parameters | Returns |
|---|---|---|
| `GET /api/v1/cities/search` | `q` (2–100 chars), `limit` (1–5, default 5) | Matching city candidates with coordinates |
| `GET /api/v1/weather/current` | `lat` (-90…90), `lon` (-180…180) | Current conditions in °C and km/h |
| `GET /api/v1/weather/forecast` | `lat`, `lon` | 3-hourly forecast points across five days |

Error statuses: `422` invalid input, `404` unknown location, `502` provider failure,
`503` missing configuration or rate limiting, `504` provider timeout.

## Deployment

`build.py` runs `npm ci` and `npm run build` so the platform serves the compiled React app from
`frontend/dist`, with FastAPI handling `/api/*` and `/docs`. Set `OPENWEATHER_API_KEY` in the
platform's environment variables — never in the repository.

## Known follow-ups

- Pin backend dependency versions in `requirements.txt`.
- Make CORS origins configurable instead of hardcoding a single deployed domain.
- Five client tests currently fail because `Settings` needs `populate_by_name=True` for
  test-injected API keys (tracked in review notes).
