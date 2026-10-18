# PLAN-001: Weather Backend MVP

**Status:** Draft — revised plan awaiting explicit product-owner approval  
**Role:** Software Architecture  
**Reviewed sources:** [Product intent](../../intent/weather-app.md), [SPEC-001](../specs/SPEC-001.md), [architect guidance](../../.agent/architect.md), and [project agent instructions](../../agent.md)  
**Target:** Backend-only MVP with REST endpoints testable in FastAPI Swagger UI at `/docs`  
**Timebox:** 2 hours, excluding API credential/access delays

> This plan reflects the clarified backend-first direction. The previous approved Intent/SPEC-001 described the full user-facing product; the revised backend-phase specification has been drafted in SPEC-001 and still awaits explicit approval. Neither this draft plan nor the revised spec is authorization to implement.

## 1. MVP objective and boundaries

Deliver a minimal Python 3.11+ / FastAPI backend that provides:

- OpenWeather city search and matching city candidates.
- Current weather for selected coordinates.
- Five-day forecast data at the provider's 3-hour intervals.
- Pydantic request validation and documented response schemas.
- Recoverable, documented HTTP errors.
- Interactive Swagger UI at `/docs` for exercising all API operations.

Frontend, browser geolocation UI, Figma integration, visual styling, deployment, database, persistence, authentication, and additional infrastructure are deferred or out of scope for this backend phase. The endpoints accept coordinates rather than invoking browser geolocation; a future frontend may obtain those coordinates after user action and pass them to the API.

## 2. Conflicts and proposed SPEC-001 amendments

### Current conflicts

| Approved document statement | Conflict with clarified backend MVP |
|---|---|
| Intent describes a user-facing web app with current conditions and forecast UI. | Immediate deliverable is a REST backend; frontend is deferred. |
| Intent/SPEC require device location initiated by a browser button. | Backend cannot obtain browser permission or coordinates; it accepts validated latitude/longitude supplied by an API caller. |
| Intent/SPEC include always-available city search and selection workflow. | The backend can return matching cities; candidate selection is a client workflow and the backend exposes coordinate-based weather endpoints. |
| SPEC acceptance criteria AC-001–AC-010 verify visible behavior, loading, responsive layout, English UI, and Figma alignment. | Those presentation criteria cannot be demonstrated by the backend-only MVP. |
| SPEC NFR-004 and Intent currently give an approximately four-hour app estimate. | The clarified two-hour limit applies to backend API work only. |
| SPEC NFR-005 says same-origin server-side proxy. | Replace the proxy concept with FastAPI as the application API that calls OpenWeather through a dedicated client. |

### SPEC-001 alignment — drafted, awaiting approval

1. **Purpose/scope:** Retitle or amend the scope to “Weather Forecast Backend MVP.” Make the deliverable the documented FastAPI REST API and Swagger UI, not a completed web UI. State that frontend, Figma, deployment, persistence, and database are deferred/out of scope for this phase.
2. **Location behavior:** Replace browser geolocation permission and UI requirements with coordinate-based backend inputs. Keep geolocation permission and the location button as future frontend behavior. Define city search as a backend operation that returns candidate places; the future client selects a candidate.
3. **Functional requirements:** Add concrete endpoint requirements for `GET /api/v1/cities/search`, `GET /api/v1/weather/current`, and `GET /api/v1/weather/forecast`; specify the contracts in Section 3 of this plan. Preserve OpenWeather, 3-hour granularity, five-day span, English, °C and km/h conventions.
4. **Error/validation requirements:** Require bounded input validation, Pydantic response models, and documented 404/422/502/503/504 behavior as defined below.
5. **Non-functional requirements:** Replace browser responsiveness, loading UI, and Figma alignment as backend-phase acceptance criteria with API contract correctness, Swagger availability, safe error responses, and credential protection. Retain the other UI requirements for the later frontend phase rather than deleting them from the product scope.
6. **Time constraint:** Change the current four-hour estimate to a two-hour backend-only timebox, with the risks and prerequisites explicitly stated.
7. **Acceptance criteria/traceability:** Replace or phase-tag UI-only ACs for this backend milestone with the proposed `BE-AC-*` criteria in Section 5. Keep UI acceptance criteria explicitly deferred to a future frontend milestone.
8. **Traceability and approval:** Update the intent-to-spec mapping and mark backend scope/delivery decisions approved only after product-owner approval. Until then, the current Intent and SPEC remain authoritative.

The prior approved product scope has not been silently changed: the revised SPEC-001 preserves the full Weather App goal and marks frontend work as deferred for this backend phase. The revised specification remains a draft pending explicit approval.

## 3. Proposed REST API contract

Prefix all application routes with `/api/v1`. FastAPI's generated Swagger UI is available at `GET /docs`; OpenAPI JSON is available at `/openapi.json`. Use Pydantic models as response models so the contracts appear in Swagger and returned payloads are validated.

### 3.1 City search

`GET /api/v1/cities/search`

| Query parameter | Type and validation | Required | Meaning |
|---|---|---:|---|
| `q` | string, trimmed, 2–100 characters after trimming | Yes | City query sent to OpenWeather Direct Geocoding |
| `limit` | integer 1–5, default 5 | No | Maximum number of matching places returned |

Calls `GET https://api.openweathermap.org/geo/1.0/direct?q={q}&limit={limit}&appid={API_KEY}`. Return an empty `results` list with `200` when no matches are found; this is a valid search result, not an upstream failure.

**Response model — `CitySearchResponse`**

| Field | Type | Notes |
|---|---|---|
| `query` | string | Normalized submitted query |
| `results` | array of `CityMatch` | May be empty; bounded by requested limit |

**`CityMatch`**

| Field | Type | Notes |
|---|---|---|
| `name` | string | Provider city/locality name |
| `state` | string or null | Included when provider supplies it |
| `country` | string | Country code |
| `latitude` | number | WGS84 latitude, -90 through 90 |
| `longitude` | number | WGS84 longitude, -180 through 180 |

### 3.2 Current weather

`GET /api/v1/weather/current`

| Query parameter | Type and validation | Required | Meaning |
|---|---|---:|---|
| `lat` | finite number, -90 through 90 | Yes | Selected city's or device's latitude |
| `lon` | finite number, -180 through 180 | Yes | Selected city's or device's longitude |

Calls `GET https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&lang=en&appid={API_KEY}`.

**Response model — `CurrentWeatherResponse`**

| Field | Type | Notes |
|---|---|---|
| `location` | `Location` | Resolved location name and coordinates |
| `observed_at` | ISO 8601 datetime | Observation time, normalized to UTC |
| `temperature_c` | number | Current temperature in Celsius |
| `feels_like_c` | number | Apparent temperature in Celsius |
| `humidity_percent` | integer | Relative humidity |
| `condition` | string | Main condition |
| `description` | string | English description |
| `wind_speed_kmh` | number or null | Convert OpenWeather metric m/s by multiplying by 3.6 |

### 3.3 Five-day forecast

`GET /api/v1/weather/forecast`

| Query parameter | Type and validation | Required | Meaning |
|---|---|---:|---|
| `lat` | finite number, -90 through 90 | Yes | Selected city's or device's latitude |
| `lon` | finite number, -180 through 180 | Yes | Selected city's or device's longitude |

Calls `GET https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units=metric&lang=en&appid={API_KEY}`. Do not set `cnt` for the normal five-day response. The provider returns forecast points every three hours (up to 40 timestamps). Do not interpolate hourly values.

**Response model — `ForecastResponse`**

| Field | Type | Notes |
|---|---|---|
| `location` | `Location` | Resolved location |
| `timezone_offset_seconds` | integer | Provider city timezone offset, when supplied |
| `items` | array of `ForecastPoint` | Provider's three-hourly timestamps across five days |

**`ForecastPoint`**

| Field | Type | Notes |
|---|---|---|
| `forecast_at` | ISO 8601 datetime | Forecast timestamp; include/normalize offset consistently |
| `temperature_c` | number | Forecast temperature in Celsius |
| `feels_like_c` | number or null | Apparent temperature when supplied |
| `humidity_percent` | integer or null | Relative humidity when supplied |
| `condition` | string | Main condition |
| `description` | string | English description |
| `wind_speed_kmh` | number or null | Convert m/s to km/h |

**Shared `Location`**

`name: string`, `country: string | null`, `latitude: number`, `longitude: number`.

These responses are a small normalized API contract, not a pass-through of OpenWeather's entire JSON. If a required section or response shape is absent, return a clear error; do not invent values.

### 3.4 HTTP error contract

Use a consistent application error body such as `{"detail": {"code": "machine_readable_code", "message": "Safe user-facing message"}}`. FastAPI's default request validation response can retain its standard `422` structure unless a custom error handler is needed; do not add a custom handler solely for cosmetic consistency.

| Status | When to return |
|---|---|
| `200 OK` | Request succeeded. Empty city matches are `200` with `results: []`. |
| `404 Not Found` | Valid coordinates have no corresponding weather location / OpenWeather reports location not found. No geocoding matches remain a `200` empty list. |
| `422 Unprocessable Entity` | Missing, malformed, too-short/long, non-finite, or out-of-range query parameters; FastAPI/Pydantic validation. |
| `502 Bad Gateway` | OpenWeather returns an unexpected upstream error/status or invalid/unusable payload. Do not expose its raw response or key. |
| `503 Service Unavailable` | `OPENWEATHER_API_KEY` is missing, or provider quota/rate limit makes the service temporarily unavailable. |
| `504 Gateway Timeout` | OpenWeather request exceeds the configured client timeout. |

Do not retry automatically in this MVP. Log only a safe correlation/context message and status; never print the API key, upstream URL query string, or raw response containing credentials.

## 4. Architecture and minimal folder structure

```text
app/
  main.py                     FastAPI app, router registration, /docs
  api/
    routes/
      weather.py              Three REST operations; HTTP mapping only
  schemas/
    weather.py                Pydantic request/response/error models
  services/
    weather_service.py        Orchestrates search, current and forecast use cases;
                               maps provider data to app contract and units
  clients/
    openweather_client.py     HTTPX calls to fixed OpenWeather endpoints,
                               timeout and upstream error translation
  core/
    config.py                 Server-only settings and API key loading
tests/
  test_weather_api.py         Swagger/API-level success, validation and errors
  test_weather_service.py     Service mapping and unit conversion
.env                          Local secret only; ignored, never committed
.env.example                  Names and non-secret setup instructions only
.gitignore                    Excludes .env and other local secret files
requirements.txt              Minimal app and test dependencies
```

### Responsibilities and request flow

- **Routes:** declare query parameters and response models; call the service; map known domain/provider errors to HTTP status. No OpenWeather parsing or business logic.
- **Pydantic schemas:** define stable, typed, validated API request/response contracts surfaced in OpenAPI.
- **WeatherService:** coordinates city search/current/forecast use cases and normalizes external values, including m/s to km/h.
- **OpenWeatherClient:** owns base URLs, fixed endpoint paths, query construction, async HTTPX calls, timeout, response parsing, and provider error translation.
- **Configuration:** reads `OPENWEATHER_API_KEY` from the server environment or ignored local `.env`; missing key is surfaced as a controlled `503`, not a success-shaped fallback.
- **FastAPI `/docs`:** provides the immediate test interface. Test city search, copy a chosen candidate's coordinates, then submit those coordinates to the current and forecast operations.

Avoid database, cache, CORS setup, frontend routes, authentication, containerization, deployment manifests, and extra services for this local backend MVP. Add only if later requirements justify them.

## 5. Proposed backend acceptance criteria and traceability

These are proposed phase-specific criteria (`BE-AC-*`), not replacements already approved in SPEC-001. They must be incorporated into an approved spec revision before implementation.

| Proposed criterion | Testable outcome | Existing source traceability |
|---|---|---|
| BE-AC-001 — Swagger | Start the backend locally; `/docs` loads and documents all three operations, query constraints, response schemas, and error codes. | SPEC NFR-005 (revised); proposed backend scope |
| BE-AC-002 — City search | Valid `q` returns `200 CitySearchResponse` with zero or more candidates and bounded results including coordinates. Swagger user can choose/copy a candidate. | SPEC FR-002, AC-004 (backend portion) |
| BE-AC-003 — Current conditions | Valid coordinate pair returns `200 CurrentWeatherResponse` with location, current conditions, Celsius and km/h values. | SPEC FR-003, FR-009; AC-001, AC-004, AC-010 (data portion) |
| BE-AC-004 — Forecast | Valid coordinate pair returns `200 ForecastResponse` containing 3-hourly points for the five-day span, not fabricated hourly data. | SPEC FR-004–FR-005; AC-001, AC-004, AC-010 (data portion) |
| BE-AC-005 — Validation | Invalid or absent city/coordinate parameters return `422`; no invalid request calls OpenWeather. | SPEC FR-006–FR-007 (API validation revision) |
| BE-AC-006 — Provider failures | Unknown weather location returns `404`; missing configuration returns `503`; upstream failure returns `502`; timeout returns `504`; error bodies are safe and documented. | SPEC FR-007–FR-008 (backend revision); AC-006–AC-007 (API portion) |
| BE-AC-007 — Key protection | The actual key is read from ignored local `.env`/server environment and is not hardcoded, committed, returned, or printed. | SPEC NFR-005 (revised) |
| BE-AC-008 — Repeatable tests | Automated tests cover response mapping, wind conversion, validation, provider failure mapping, and all three route contracts without live provider calls. | Proposed backend testing NFR |

**Deferred to frontend phase:** original AC-001 browser permission/button behavior, user-visible loading and recovery copy (AC-002–AC-006), responsive layout AC-008, Figma AC-009, and rendered language/unit presentation. Backend data conventions (English descriptions, Celsius, km/h) are verified in BE-AC-003/004; visual behavior is not claimed as delivered by the API.

## 6. Ordered implementation tasks (2-hour target)

The estimate assumes Python 3.11+ is available, dependencies can be installed, the OpenWeather key is active, and no external access/setup waits consume the timebox.

| Order | Task | Estimate | Depends on | Traceability |
|---|---|---:|---|---|
| 1 | Confirm backend-only spec amendment, Python version, active OpenWeather access, and local run command; create the minimum FastAPI package/test skeleton. | 15 min | — | Proposed backend scope; BE-AC-001 |
| 2 | Add only required dependencies and secure local configuration: FastAPI, Uvicorn, HTTPX, Pydantic Settings / dotenv support, pytest; ignore `.env`; create a blank `.env.example`. | 15 min | 1 | BE-AC-007; NFR security amendment |
| 3 | Define Pydantic contracts and implement the async OpenWeather client for geocoding/current/forecast, with fixed URLs, request timeout, key/config checks, and safe upstream errors. | 30 min | 2 | BE-AC-002–004, BE-AC-006–007 |
| 4 | Implement WeatherService and the three FastAPI routes with query constraints, response models, documented status codes, and `/docs`. | 30 min | 3 | BE-AC-001–006 |
| 5 | Add focused automated route/service tests using mocked HTTPX transport; verify error mappings and unit conversion. | 20 min | 3–4 | BE-AC-002–006, BE-AC-008 |
| 6 | Run tests and app, exercise all endpoints in Swagger, inspect logs/diff for secret leakage, and update a short local run note if needed. | 10 min | 2–5 | BE-AC-001–008 |
|  | **Total** | **120 min** |  |  |

This is a tight but plausible backend-only MVP estimate, not a guarantee. Do not spend this phase implementing React, Figma, deployment, persistence, or unrelated infrastructure.

## 7. Test plan

1. **Route contract tests with FastAPI TestClient:** status, schema shape, query validation, empty city results, candidate results, current result, forecast result.
2. **Client/service unit tests:** mocked OpenWeather responses; expected query construction; city coordinates; UTC/offset timestamp normalization; wind conversion from m/s to km/h; malformed/partial provider payload handling.
3. **HTTP error tests:** unknown location, invalid key/upstream rejection, rate limiting, malformed upstream response, missing local key, and timeout map to documented statuses without leaking provider detail.
4. **No-live-network test guarantee:** use an injected/mock HTTPX transport so automated tests neither consume OpenWeather quota nor require credentials.
5. **Swagger smoke test:** run the app, open `/docs`, execute city search, then use a returned match's coordinates in current and forecast operations. Confirm documentation shows query validation and response/error contracts.
6. **Secret hygiene check:** verify `.env` is ignored and absent from changes; check source, stdout/stderr, API responses, and test output for the key. Use only a dummy value in tests.

FastAPI documents automatic Swagger UI at `/docs`, Pydantic response models, `Query` validation, `HTTPException` error handling, and endpoint tests with `TestClient`. Reference: [FastAPI docs](https://fastapi.tiangolo.com/), [Testing](https://fastapi.tiangolo.com/tutorial/testing/), [Query validation](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/).

## 8. Risks and unresolved decisions

- **Specification approval is the primary blocker:** approved Intent/SPEC still describe a user-facing app. Do not implement this backend phase until the proposed scope and acceptance-criteria revision is explicitly approved.
- **Credential/access:** the API key must be provided through an ignored local `.env` or server environment. Missing, inactive, or unentitled credentials block live Swagger integration; mocked tests can still validate contract behavior.
- **Python environment/dependency install:** the workspace currently contains only documentation, and no Python version or environment setup has been verified. Interpreter/dependency setup may exceed the 15-minute setup estimate.
- **Two-hour timebox:** 120 minutes includes creating the backend scaffold from an empty code workspace. It is aggressive; cut no approved backend requirements silently. If setup, API access, or debugging runs long, surface the estimate miss and request scope/time direction.
- **OpenWeather quota/access:** published Free plan includes current conditions, geocoding, and 5-day/3-hour forecast (60 calls/minute and up to 1,000,000/month); actual key status and current account access still need confirmation. City search plus one weather lookup uses three provider requests.
- **Timezone representation:** preserve forecast timestamps and provider timezone offset clearly; confirm whether response timestamps should be ISO UTC plus offset metadata or retain provider-local representation before freezing the API schema.
- **Response contract detail:** the proposed schemas are intentionally minimal. Any additional fields (precipitation probability, icons, daily summaries, units preferences) require explicit scope approval.
- **No `AGENTS.md` found:** the project file search found no `AGENTS.md`; `.agent/architect.md` and `agent.md` were reviewed. `agent.md` identifies FastAPI/backend-first priorities, but also retains React-oriented implementation guidance and the earlier four-hour estimate; reconcile those for consistency after the backend scope revision is approved. The workspace has no package manifest or source, so Python/dependency setup may exceed estimates.

No containerization, deployment topology, database, or ADR is required for the local backend MVP. Revisit these only if later delivery needs them.

## 9. Rollback strategy

- Keep provider communication behind `OpenWeatherClient` and orchestration behind `WeatherService`. If upstream mapping is defective, revert or disable that integration independently of route schemas.
- If an endpoint change breaks the API contract, revert the route/service change to the last working version and use mocked responses until the provider behavior is resolved.
- If the key is exposed, revoke/rotate it with OpenWeather immediately, update the ignored local environment value, and restart the app. Removing it from source history alone is not sufficient.
- Since this is a local backend MVP, rollback means restoring the last known-good source revision and local secret configuration; no deployment rollback is in scope.

## 10. Review and approval

**Draft only.** This plan is not product-owner-approved. Review and explicitly approve the revised SPEC-001 and this implementation plan before implementation. The approved product intent remains the overall goal; its frontend scope is deferred for this phase.
