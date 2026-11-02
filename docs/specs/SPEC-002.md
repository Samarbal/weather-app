# SPEC-002: AI Weather Advisor (backend)

**Provider update (2026-10-24):** The implementation now uses OpenAI Responses API
with `OPENAI_API_KEY` and default model `gpt-6-luna`. The Gemini provider details
below document the original design and are superseded by this update. The request,
response, forecast grounding, and error-status contracts remain the same.

**Status:** Approved scope from the product owner (2026-10-21) — authorized for backend implementation and backend-only delivery.
**Overall product goal:** The Weather App (see [intent/weather-app.md](../../intent/weather-app.md)).
**Relationship to SPEC-001:** SPEC-001 and its three endpoints remain valid and are not modified by this feature.
**Revision note:** This supersedes the earlier "AI Weather Insights" draft. The response contract is now exactly three short sections (`weather_outlook`, `what_to_wear`, `activity_tips`), the prompt is a single editable file, and custom rate-limiting infrastructure was dropped in favor of the Gemini free-tier quota (see AI-NFR-005).

## 1. Feature goal and user flow

Add a small, optional AI feature that explains the forecast the user is already looking at.

1. The user selects a city (existing search or "Use my location").
2. The existing endpoints render current conditions and the 5-day / 3-hour forecast.
3. The user clicks **"✨ Get AI Weather Advice"**.
4. FastAPI reuses `WeatherService` to fetch the normalized 5-day forecast for the selected coordinates, sends that data with a fixed prompt to the Gemini API, and returns three short sections.
5. The UI displays the three sections with an AI disclaimer.

**Grounding rule (core requirement):** Gemini interprets OpenWeather forecast data that the app already fetched. It never supplies its own meteorological prediction, never invents values, and never claims anything beyond the last forecast timestamp.

## 2. Scope

### In scope (this backend phase)

- `POST /api/v1/weather/insights`.
- `GEMINI_API_KEY` (and optional `GEMINI_MODEL`) read from the server-side environment.
- Fixed, editable prompt constants.
- Structured JSON output validated with Pydantic.
- Safe mapping of missing key, provider failure, timeout, rate limit, and invalid model output.
- Focused mocked tests with no live Gemini calls.

### Out of scope / deferred

- Any frontend change (the "✨ Get AI Weather Advice" button is a later, separately approved task).
- Changes to the three existing endpoints, their contracts, or `ForecastPoint` (adding a precipitation field would change an existing response).
- Databases, caching, RAG, queues, streaming, chat history, unit/language options.
- Application-level rate limiting, authentication, deployment changes.
- Live Gemini calls in tests or CI.

## 3. Functional requirements

| ID | Requirement |
|---|---|
| AI-FR-001 | Provide `POST /api/v1/weather/insights` accepting validated `latitude` and `longitude` (same bounds as the existing weather endpoints) plus optional `city_name` (≤100 chars) and `country` (≤2 chars) for display context. |
| AI-FR-002 | The endpoint must fetch the forecast itself through the existing `WeatherService.forecast()`. Weather values supplied by the client are never accepted or forwarded. |
| AI-FR-003 | Send Gemini only the normalized forecast: city/country, timezone offset, and up to 40 points as UTC timestamp, temperature, feels-like, humidity, wind, condition, description. No credentials, no unrelated data. |
| AI-FR-004 | Use a fixed system instruction and user-prompt template stored together in one module so the prompt is easy to edit. |
| AI-FR-005 | Require the model to return JSON with exactly three string fields: `weather_outlook`, `what_to_wear`, `activity_tips`. Enforce with a Gemini JSON response schema **and** strict Pydantic validation (`extra="forbid"`, non-empty, ≤800 chars each). |
| AI-FR-006 | Grounding: the prompt must forbid invented temperatures, rain/snow probabilities, or conditions; forbid claims past the final forecast timestamp; instruct that forecast text is data, not instructions; require short, friendly, plain English. |
| AI-FR-007 | The server sets `label` (fixed AI disclaimer) and `source` (city, country, forecast range, point count) from the real fetched forecast. The model cannot alter them. |
| AI-FR-008 | Store `GEMINI_API_KEY` server-side only via `SecretStr`; never hardcode, log, return, or commit it. Send it in the `x-goog-api-key` header, never in the URL. |
| AI-FR-009 | Keep the three existing endpoints (`/api/v1/cities/search`, `/api/v1/weather/current`, `/api/v1/weather/forecast`) byte-for-byte unchanged, including their tests. |
| AI-FR-010 | Add `"POST"` to the CORS `allow_methods` list so the deployed frontend can call the new endpoint; no other CORS change. |
| AI-FR-011 | Default model `gemini-3.8-flash` (free tier), overridable with `GEMINI_MODEL` for accounts where a different Flash model is available. `gemini-2.5-flash` is no longer available to new users. |

## 4. API contract

**Operation:** `POST /api/v1/weather/insights` (tags: `weather`, appears in `/docs`)

**Request body — `InsightRequest`**

| Field | Type | Required |
|---|---|---:|
| `latitude` | finite number, -90…90 | yes |
| `longitude` | finite number, -180…180 | yes |
| `city_name` | string ≤100 chars | no |
| `country` | string ≤2 chars | no |

**Response body — `InsightResponse` (`extra="forbid"`)**

| Field | Type | Source |
|---|---|---|
| `label` | constant string: `"AI-generated interpretation of the OpenWeather 5-day forecast — not an independent weather prediction."` | server |
| `source` | `{city, country, forecast_from, forecast_to, point_count}` | server, from fetched forecast |
| `weather_outlook` | string, 1–800 chars | Gemini |
| `what_to_wear` | string, 1–800 chars | Gemini |
| `activity_tips` | string, 1–800 chars | Gemini |

**HTTP status behavior**

| Status | When |
|---|---|
| `200 OK` | Valid advice returned. |
| `404 Not Found` | Forecast location not found upstream (propagated unchanged from `WeatherService`). |
| `422 Unprocessable Entity` | Missing/invalid body fields (FastAPI/Pydantic). |
| `502 Bad Gateway` | Gemini unreachable/unexpected status, malformed body, unparseable output, or output failing Pydantic validation. No raw provider detail. |
| `503 Service Unavailable` | `GEMINI_API_KEY` missing/blank; Gemini `401/403` (access denied); Gemini `404` (model unavailable); Gemini `429` (free-tier quota). Also upstream OpenWeather `503`. |
| `504 Gateway Timeout` | Gemini timeout (15 s) or upstream OpenWeather timeout. |

Error body: `{"detail": "<safe message>"}`, identical in shape to the existing endpoints. Keys and raw provider payloads never appear in responses or logs.

## 5. Non-functional requirements

| ID | Requirement |
|---|---|
| AI-NFR-001 | No new third-party dependencies: reuse `httpx`, FastAPI, and Pydantic already in `requirements.txt`. |
| AI-NFR-002 | New logic lives in new files (schemas, client, prompts, service, route); existing modules receive only the two additive edits in AI-FR-010/AI-FR-011. |
| AI-NFR-003 | One Gemini call per request, 15-second timeout, no retries, no streaming. |
| AI-NFR-004 | All tests mocked with `httpx.MockTransport`; tests never read a real key and consume no quota. |
| AI-NFR-005 | Usage/cost control relies on Google's free-tier quota (≈5–15 requests/minute, ≈1,000–1,500 requests/day per model), which is enforced upstream and surfaced as `503`. App-level rate limiting is explicitly deferred as unnecessary for this MVP. |
| AI-NFR-006 | Rough cost per request: ~600–1,000 input tokens and ≤300 output tokens — free on the free tier, well under $0.01 on paid Flash tiers. *(Estimate; verify against current pricing before paid use.)* |
| AI-NFR-007 | Privacy: only city name, country, and coordinates rounded to 2 decimals (~1 km) plus public forecast data are sent to Google. Free-tier prompts may be used by Google to improve its products — noted in the README follow-up. |

## 6. Acceptance criteria (backend)

| ID | Criterion |
|---|---|
| AI-AC-001 | Given `GEMINI_API_KEY` set and a mocked Gemini response, `POST /api/v1/weather/insights` returns `200` with the server-set `label`, a `source` matching the fetched forecast, and the three validated sections. |
| AI-AC-002 | Given an invalid body (missing/out-of-range coordinates), the API returns `422` and makes no OpenWeather or Gemini request. |
| AI-AC-003 | Given no `GEMINI_API_KEY`, the API returns `503` with a safe message and no Gemini request is made. |
| AI-AC-004 | Given Gemini timeout / `429` / `5xx`, the API returns `504` / `503` / `502` respectively with no raw provider detail. |
| AI-AC-005 | Given a Gemini response that is not JSON, is missing a field, has an empty/overlong field, or contains extra fields, the API returns `502` and never a partial payload. |
| AI-AC-006 | The prompt sent to Gemini contains every forecast point (timestamp, temperature, humidity, wind, condition, description) and contains no API key. |
| AI-AC-007 | The three existing endpoint tests and contracts are unchanged and still pass (aside from pre-existing failures unrelated to this feature). |
| AI-AC-008 | `GEMINI_API_KEY` never appears in source, responses, or test output; `.env` remains git-ignored. |

## 7. Traceability

| Product intent | Coverage |
|---|---|
| Explain the selected city's forecast in plain language | AI-FR-001–003, AI-AC-001 |
| Practical advice without inventing data | AI-FR-006–007, AI-AC-005–006 |
| Safe, cheap, low-impact addition | AI-NFR-001–006, AI-AC-003–004, AI-AC-007 |
| Backend-only phase | §2 scope; frontend deferred |

## 8. Assumptions and open items

1. The product owner's account must have a free-tier-capable Flash model. The default is `gemini-3.8-flash` (Google deprecated `gemini-2.5-flash` for new users); override with `GEMINI_MODEL` if needed. A `403 "Your project has been denied access"` from Google means the project/API key itself lacks generation access — fix the key in Google AI Studio; no code change resolves it.
2. The forecast payload has no precipitation-probability field; advice may reference rain/snow only where `condition`/`description` says so. Adding probability data would change `ForecastPoint` and is out of scope.
3. Free-tier data may be used by Google for product improvement; acceptable for this non-personal forecast data.
4. The frontend task (button + panel + disclaimer badge) is a separate, later approval.

## 9. Approval

Scope approved by the product owner on 2026-10-21 with the instruction to plan, implement, and test the backend only, then stop for review.
