# SPEC-001: Weather App — Backend MVP

**Status:** Draft — revised backend-phase specification awaiting product-owner approval  
**Overall product goal:** A simple, clear Weather App that helps people quickly understand local weather.  
**Current phase:** Backend MVP; frontend and Figma implementation are deferred.

## 1. Product goal and phased scope

### Overall product goal

Build a simple, clear Weather App for anyone who wants a quick local forecast. The completed product will support city search, optional user-initiated device location, current conditions, a 3-hourly forecast, and a 5-day forecast. The eventual user interface will be in English, display temperature in Celsius and wind speed in km/h, and be responsive to common screen sizes.

### Backend MVP in this phase

Deliver a Python 3.11+ FastAPI REST API that retrieves OpenWeather city matches, current conditions, and five-day/3-hourly forecast data. Expose Pydantic schemas and interactive Swagger UI at `/docs` so endpoints can be explored and tested directly.

The backend accepts a city query or coordinates. It does not request browser location permission; a future frontend may request location after an explicit user action and send coordinates to this API. City search returns matching candidates; selecting a match is a future client workflow.

### Deferred product scope

The following remain part of the overall Weather App goal but are not deliverables or acceptance criteria for this backend phase:

- React/web frontend, UI loading and error presentation, responsive layout, and Figma integration.
- Browser geolocation permission and user interaction.
- Frontend selection/rendering of city-match choices.
- Hosting/deployment.
- Database, persistence, accounts, saved locations, alerts, maps, and historical weather.

## 2. Functional requirements

| ID | Requirement | Priority / phase |
|---|---|---|
| FR-001 | Provide `GET /api/v1/cities/search` accepting a city query and optional bounded result limit. Return matching city names, optional state, country, and coordinates from OpenWeather Direct Geocoding. A valid query with no matches returns an empty result list. | Must — backend |
| FR-002 | Provide `GET /api/v1/weather/current` accepting validated latitude and longitude and returning a normalized current-weather response for those coordinates. | Must — backend |
| FR-003 | Provide `GET /api/v1/weather/forecast` accepting validated latitude and longitude and returning normalized forecast points from the OpenWeather five-day/3-hour endpoint. Do not interpolate hourly data. | Must — backend |
| FR-004 | Use English descriptions, Celsius temperature values, and wind speed in km/h in current and forecast response schemas. Convert OpenWeather metric wind speed from m/s to km/h. | Must — backend |
| FR-005 | Validate request parameters and upstream response shapes. Do not return fabricated or success-shaped fallback data for invalid requests, missing configuration, or unusable upstream responses. | Must — backend |
| FR-006 | Return documented, safe HTTP errors for invalid input, unknown locations, missing server configuration, upstream failure, and upstream timeout. Do not expose API credentials or raw provider diagnostics. | Must — backend |
| FR-007 | Expose automatically generated OpenAPI documentation and Swagger UI at `/docs`, including endpoint parameters, response schemas, and documented error statuses. | Must — backend |
| FR-008 | Read the OpenWeather key from the server-side environment variable named `OPENWEATHER_API_KEY`. The developer supplies the value locally; it must not be hardcoded, printed, returned to callers, or committed. | Must — backend |
| FR-009 | The completed Weather App will let users request device location through an explicit user action and will keep city search available. The backend phase supports the future workflows through its coordinate and city-search operations; browser behavior is deferred. | Future frontend |
| FR-010 | The completed Weather App will present current conditions, 3-hourly forecast points, and a 5-day forecast in a simple, responsive interface with English text, Celsius temperatures, and km/h wind speeds. | Future frontend |

## 3. API contract

All application routes are under `/api/v1`. Swagger UI is at `GET /docs`; the OpenAPI document is at `GET /openapi.json`. FastAPI/Pydantic validation and response models must be reflected in the generated API documentation.

### 3.1 City search

**Operation:** `GET /api/v1/cities/search`

| Query parameter | Type and validation | Required | Default |
|---|---|---:|---|
| `q` | String, trimmed, 2–100 characters after trimming | Yes | — |
| `limit` | Integer from 1 through 5 | No | 5 |

Upstream: `GET https://api.openweathermap.org/geo/1.0/direct?q={q}&limit={limit}&appid={OPENWEATHER_API_KEY}`.

**Response model — `CitySearchResponse`**

| Field | Type | Notes |
|---|---|---|
| `query` | string | Normalized submitted query |
| `results` | array of `CityMatch` | Empty if there are no matches; no longer than requested limit |

**`CityMatch`**

| Field | Type | Notes |
|---|---|---|
| `name` | string | City/locality name |
| `state` | string or null | Included when supplied |
| `country` | string | Country code |
| `latitude` | number | WGS84 latitude, -90 through 90 |
| `longitude` | number | WGS84 longitude, -180 through 180 |

### 3.2 Current weather

**Operation:** `GET /api/v1/weather/current`

| Query parameter | Type and validation | Required |
|---|---|---:|
| `lat` | Finite number from -90 through 90 | Yes |
| `lon` | Finite number from -180 through 180 | Yes |

Upstream: `GET https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&lang=en&appid={OPENWEATHER_API_KEY}`.

**Response model — `CurrentWeatherResponse`**

| Field | Type | Notes |
|---|---|---|
| `location` | `Location` | Resolved place and coordinates |
| `observed_at` | ISO 8601 datetime | Normalized to UTC |
| `temperature_c` | number | Celsius |
| `feels_like_c` | number | Celsius |
| `humidity_percent` | integer | Relative humidity |
| `condition` | string | Main condition |
| `description` | string | English description |
| `wind_speed_kmh` | number or null | Metric API m/s converted by ×3.6 |

### 3.3 Five-day forecast

**Operation:** `GET /api/v1/weather/forecast`

| Query parameter | Type and validation | Required |
|---|---|---:|
| `lat` | Finite number from -90 through 90 | Yes |
| `lon` | Finite number from -180 through 180 | Yes |

Upstream: `GET https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units=metric&lang=en&appid={OPENWEATHER_API_KEY}`. Omit `cnt` to use the normal five-day response. OpenWeather returns three-hourly points (up to 40 timestamps); do not interpolate hourly values.

**Response model — `ForecastResponse`**

| Field | Type | Notes |
|---|---|---|
| `location` | `Location` | Resolved place |
| `timezone_offset_seconds` | integer | Provider timezone offset, when present |
| `items` | array of `ForecastPoint` | Three-hourly points over the five-day forecast period |

**`ForecastPoint`**

| Field | Type | Notes |
|---|---|---|
| `forecast_at` | ISO 8601 datetime | Forecast timestamp with a documented, consistent timezone representation |
| `temperature_c` | number | Celsius |
| `feels_like_c` | number or null | Celsius, when available |
| `humidity_percent` | integer or null | When available |
| `condition` | string | Main condition |
| `description` | string | English description |
| `wind_speed_kmh` | number or null | m/s converted to km/h |

**Shared `Location`:** `name: string`, `country: string | null`, `latitude: number`, `longitude: number`.

These are normalized application response schemas, not a pass-through of the entire OpenWeather payload.

### 3.4 HTTP status and error behavior

| Status | Meaning |
|---|---|
| `200 OK` | Request succeeded. A city search with zero results returns `200` and `results: []`. |
| `404 Not Found` | Weather location cannot be resolved for valid coordinates. No city matches are not a `404`. |
| `422 Unprocessable Entity` | Missing, malformed, too-short/long, non-finite, or out-of-range query parameters, following FastAPI/Pydantic validation. |
| `502 Bad Gateway` | Unexpected OpenWeather upstream failure or malformed/unusable provider payload. Do not return raw provider diagnostics. |
| `503 Service Unavailable` | `OPENWEATHER_API_KEY` is missing, or OpenWeather rate limiting/quota prevents service. |
| `504 Gateway Timeout` | OpenWeather request exceeds the configured timeout. |

Application errors should use a safe, stable shape such as `{"detail":{"code":"machine_readable_code","message":"Safe message"}}`. FastAPI's standard `422` validation response may be retained. Error responses and logs must never include the API key, upstream URL query string, or raw credential-bearing provider data.

## 4. Non-functional requirements

| ID | Requirement | Priority / phase |
|---|---|---|
| NFR-001 | Keep the backend limited to the three weather API operations, request validation, response normalization, Swagger documentation, and core automated tests. | Must — backend |
| NFR-002 | Use distinct route, Pydantic schema, service, OpenWeather client, and configuration responsibilities; avoid database, deployment, cache, authentication, containerization, and other infrastructure in this phase. | Must — backend |
| NFR-003 | Complete the backend MVP within a 2-hour development timebox, assuming Python 3.11+ and dependencies are available and the OpenWeather key is already active. Surface schedule risk rather than silently removing scope. | Constraint — backend |
| NFR-004 | Keep `OPENWEATHER_API_KEY` server-side in an ignored local `.env` file or server environment. Never hardcode, print, return, or commit its value. Commit only a blank `.env.example` if setup documentation is useful. | Must — backend |
| NFR-005 | The eventual frontend must be simple, visually clear, responsive, and aligned with the product owner's Figma designs when supplied. | Future frontend |

## 5. Backend MVP acceptance criteria

These criteria apply to the current backend phase. Future frontend acceptance criteria are in Section 6.

### BE-AC-001 — Swagger

- Given the backend is running locally,
- when a user opens `/docs`,
- then Swagger UI loads and documents the three operations, query constraints, response schemas, and error statuses.

### BE-AC-002 — City search

- Given a valid city query,
- when `GET /api/v1/cities/search` is called,
- then the API returns `200 CitySearchResponse` with zero or more bounded city matches, each with available identifying fields and coordinates.

### BE-AC-003 — Current conditions

- Given valid latitude and longitude,
- when `GET /api/v1/weather/current` is called,
- then the API returns `200 CurrentWeatherResponse` with location, current conditions, Celsius temperatures, and wind speed in km/h.

### BE-AC-004 — Forecast

- Given valid latitude and longitude,
- when `GET /api/v1/weather/forecast` is called,
- then the API returns `200 ForecastResponse` with the OpenWeather five-day forecast points at three-hour intervals and does not fabricate hourly values.

### BE-AC-005 — Input validation

- Given a missing or invalid required parameter, a city query outside the allowed length, a result limit outside 1–5, or out-of-range/non-finite coordinates,
- when the API is called,
- then it returns `422` and makes no upstream request for that invalid input.

### BE-AC-006 — Provider errors

- Given an unknown weather location, missing API-key configuration, upstream failure, provider rate limit, malformed provider payload, or timeout,
- when the corresponding API operation is called,
- then it returns the documented `404`, `503`, `502`, or `504` status as applicable with a safe error response and no raw credential-bearing diagnostics.

### BE-AC-007 — Credential protection

- Given the developer supplies the API key in ignored local `.env` under the name `OPENWEATHER_API_KEY`,
- when the service calls OpenWeather,
- then the key is used only server-side and is never hardcoded, committed, returned by the API, or printed in logs/test output.

### BE-AC-008 — Automated tests

- Given the backend test suite runs without live OpenWeather access,
- when HTTPX transport and provider responses are mocked,
- then tests cover all three endpoint contracts, query validation, service mapping, wind conversion, and provider error mapping without consuming API quota.

## 6. Future frontend phase acceptance criteria

These remain part of the full Weather App product goal but are deferred and are not backend MVP release gates:

- **FE-AC-001 — User-initiated location:** A location action requests browser geolocation only after user selection; successful coordinates can be used with the current and forecast API operations.
- **FE-AC-002 — Location denied/unavailable:** Show a clear recovery path and keep city search available.
- **FE-AC-003 — City selection:** City search remains available; display matching choices and load weather for the selected candidate's coordinates.
- **FE-AC-004 — Loading and recovery:** Show loading, error, and missing-section states without a blank or frozen interface.
- **FE-AC-005 — Responsive layout:** Current conditions, 3-hourly points, and five-day forecast are usable on common mobile and desktop viewports.
- **FE-AC-006 — Figma alignment:** Match approved Figma designs when supplied.
- **FE-AC-007 — Display conventions:** Use English interface text, Celsius, and km/h.

## 7. Traceability to the overall product intent

| Overall intent | Backend phase coverage | Deferred frontend coverage |
|---|---|---|
| Quick local forecast for anyone | Current/forecast API responses; BE-AC-003–004 | FE-AC-004–005 |
| Device-location forecast after user action | Coordinate parameters accepted by current/forecast operations | FE-AC-001–002 |
| City search always available and matching city choice | Geocoding candidate operation; BE-AC-002 | FE-AC-003 |
| Current, 3-hourly, and five-day information | BE-AC-003–004 | FE-AC-004–005 |
| Clear loading, empty, and error behavior | HTTP validation/provider errors; BE-AC-005–006 | FE-AC-004 |
| English, °C, and km/h | Normalized backend response contracts; BE-AC-003–004 | FE-AC-007 |
| Simple, responsive, Figma-aligned web interface | Not in backend phase | FE-AC-005–006 |
| Two-hour backend MVP | NFR-001–003; BE-AC-001–008 | Separate frontend estimate required |

## 8. Assumptions and unresolved decisions

1. **Timezone representation:** Confirm whether timestamps are returned as UTC (`Z`) with `timezone_offset_seconds` metadata or as ISO 8601 values with the provider's local offset. The response must be consistent and documented.
2. **Minimal response fields:** The schemas above intentionally include only basic current/forecast details. Precipitation probability, icons, daily summaries, or user-selectable units are not included without explicit scope approval.
3. **Local runtime:** Python 3.11+ and required packages must be available or installable inside the two-hour timebox. The backend is tested locally; deployment is deferred.
4. **API key handling:** The developer already has an OpenWeather API key and will place its value in the local ignored `.env` file as `OPENWEATHER_API_KEY`. The key value is not part of this specification or repository.
5. **Provider access/quota:** Confirm the provided key is active for Current Weather, Direct Geocoding, and 5 Day / 3 Hour Forecast. A city search uses one provider call; each current or forecast operation uses one provider call.

## 9. Approval

This backend-phase revision is a **draft pending explicit product-owner approval**. The full Weather App remains the overall goal; frontend requirements are deferred, not removed. No implementation is authorized by this draft alone.
