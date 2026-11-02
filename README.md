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
- AI Weather Advisor endpoint that interprets the fetched five-day forecast
- Loading, empty, and error states throughout — no blank or frozen screens
- English UI, Celsius temperatures, km/h wind speeds, responsive layout

## Tech stack

- **Backend:** Python 3.11+, FastAPI, Pydantic, HTTPX — Swagger UI at `/docs`
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, lucide-react
- **Weather data:** OpenWeather (Current Weather, Direct Geocoding, 5 Day / 3 Hour Forecast)
- **AI insights:** OpenAI Responses API with structured output
- **No database** — the app is a read-only proxy over OpenWeather

## Project structure

```text
app/
  main.py                       FastAPI app, CORS, health check, built frontend hosting
  api/routes/weather.py         City search, current weather, and forecast endpoints
  api/routes/insights.py        AI Weather Advisor endpoint
  clients/                      OpenWeather and OpenAI HTTP clients
  core/config.py                Server-side settings and API key loading
  schemas/                      Validated request and response models
  services/                     Weather and forecast-grounded AI logic
frontend/                       React + TypeScript + Vite application
tests/                          Mocked client, service, and route tests
docs/specs/ and docs/plans/     Product specifications and implementation plans
intent/                         Product intent
```

## Getting started

### Requirements

- Python 3.11 or newer
- Node.js and npm
- An OpenWeather API key for live weather data
- An OpenAI API key for AI weather advice (optional if you do not use that endpoint)

### 1. Configure and run the backend

From the repository root, create and activate a virtual environment, then install
the Python dependencies:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` from the example and add your keys:

```powershell
Copy-Item .env.example .env
# Edit .env and set OPENWEATHER_API_KEY.
# Set OPENAI_API_KEY too if you want to use AI weather advice.
```

Start the API:

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation is
at [`/docs`](http://127.0.0.1:8000/docs), and the health check is
[`/health`](http://127.0.0.1:8000/health).

| Variable | Required for | Default |
|---|---|---|
| `OPENWEATHER_API_KEY` | City search, current weather, and forecast | None |
| `OPENAI_API_KEY` | AI Weather Advisor | None |
| `OPENAI_MODEL` | AI Weather Advisor | `gpt-6-luna` |
| `OPENAI_TIMEOUT_SECONDS` | AI Weather Advisor request timeout | `45` |

Keys are read only by the backend from the process environment or the ignored root
`.env` file. Do not put keys in frontend files or commit them.

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite prints the local URL (normally `http://localhost:5173`) and proxies `/api`
requests to the backend at `127.0.0.1:8000`.

To create a production frontend build:

```bash
npm run build
```

The build is written to `frontend/dist` and is served by FastAPI when present.

### 3. Tests

From the repository root, with the backend dependencies installed:

```bash
python -m pytest
```

Tests use mocked HTTP transports and do not call OpenWeather or OpenAI, so they run
offline without consuming provider quota.

## API

All application routes are under `/api/v1`.

| Method & path | Parameters | Returns |
|---|---|---|
| `GET /api/v1/cities/search` | `q` (2–100 chars), `limit` (1–5, default 5) | Matching city candidates with coordinates |
| `GET /api/v1/weather/current` | `lat` (-90…90), `lon` (-180…180) | Current conditions in °C and km/h |
| `GET /api/v1/weather/forecast` | `lat`, `lon` | 3-hourly forecast points across five days |
| `POST /api/v1/weather/insights` | JSON body with `latitude`, `longitude`, optional `city_name` and `country` | Forecast-based outlook, clothing advice, and activity tips |

Error statuses: `422` invalid input, `404` unknown location, `502` provider failure,
`503` missing configuration or rate limiting, `504` provider timeout.

## Deployment

`build.py` runs `npm ci` and `npm run build` so the platform serves the compiled React app from
`frontend/dist`, with FastAPI handling `/api/*` and `/docs`. Set `OPENWEATHER_API_KEY` in the
platform's environment variables — never in the repository.

## Project documentation

- [Product intent](intent/weather-app.md)
- [Weather API specification](docs/specs/SPEC-001.md)
- [AI Weather Advisor specification](docs/specs/SPEC-002.md)
- [Implementation plans](docs/plans/)
