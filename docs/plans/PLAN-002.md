# PLAN-002: AI Weather Advisor (backend)

**Status:** Draft → approved for execution together with [SPEC-002](../specs/SPEC-002.md) (product owner instruction: plan, implement backend only, test, stop for review).
**Role:** Software architecture
**Sources:** [SPEC-002](../specs/SPEC-002.md), [SPEC-001](../specs/SPEC-001.md), [intent](../../intent/weather-app.md), [agent.md](../../agent.md), [.agent/architect.md](../../.agent/architect.md)
**Timebox:** ~2 hours backend (implementation + mocked tests)

## 1. Objective and boundaries

Add `POST /api/v1/weather/insights`, which reuses the existing forecast pipeline and calls Gemini once to produce three short, grounded sections. No new dependencies, no frontend work, no changes to the three existing endpoints.

## 2. Design decisions (necessary for an actionable plan)

| Decision | Choice | Why |
|---|---|---|
| Who fetches weather | The endpoint, via existing `WeatherService.forecast()` | Client never supplies weather values; grounding is structural |
| Transport to Gemini | Direct `httpx` REST call to `v1beta/models/{model}:generateContent` | Avoids an SDK dependency (AI-NFR-001) |
| Auth placement | `x-goog-api-key` header | Key never appears in a URL, proxy logs, or history |
| Structured output | Gemini `generationConfig.responseSchema` + `responseMimeType: application/json`, then strict Pydantic (`extra="forbid"`) | Two-layer validation → AI-AC-005 |
| Prompt location | Single module `app/services/insight_prompts.py` | "Easy to edit" requirement |
| Provenance/disclaimer | `label` + `source` set by our code, not the model | Disclaimer and forecast range are always truthful |
| Model | `gemini-3.8-flash` default, `GEMINI_MODEL` override | Free tier keeps Flash models only; `gemini-2.5-flash` deprecated for new users (Google directs to `gemini-3.8-flash`) |
| Usage limits | Rely on Google free-tier quota; map `429 → 503` | Simplest thing that satisfies cost control (AI-NFR-005) |
| Rate limiting | Deferred | Not in approved scope; avoids unnecessary architecture |

**Notable risk carried into implementation:** `app/core/config.py` uses `validation_alias` without `populate_by_name`, so programmatic `Settings(...)` overrides are ignored (root cause of the 5 pre-existing failing tests). This plan does **not** change config behavior: `GeminiClient` accepts optional constructor parameters (`api_key`, `model`, `transport`) so tests are deterministic without touching `.env`. The pre-existing failures stay out of scope and are reported, not fixed.

## 3. File plan

```text
New
  app/schemas/insight.py          InsightRequest, InsightSource, WeatherAdvice,
                                  InsightResponse, AI_LABEL
  app/clients/gemini_client.py    GeminiClientError, GeminiClient.generate_json()
                                  (HTTPX, 15 s timeout, error translation, JSON parse)
  app/services/insight_prompts.py SYSTEM_INSTRUCTION, USER_PROMPT_TEMPLATE,
                                  INSIGHT_RESPONSE_SCHEMA,
                                  build_forecast_block(), build_user_prompt()
  app/services/insight_service.py InsightService.advise() — fetch forecast,
                                  build prompt, call Gemini, validate, assemble
  app/api/routes/insights.py      POST /api/v1/weather/insights + error mapping
  tests/test_gemini_client.py
  tests/test_insight_service.py
  tests/test_insights_routes.py

Edited (additive only)
  app/core/config.py              GEMINI_API_KEY (SecretStr|None), GEMINI_MODEL (default
                                  "gemini-2.5-flash")
  app/main.py                     register insights router; allow_methods ["GET","POST"]
  .env.example                    blank GEMINI_API_KEY= + commented GEMINI_MODEL

Untouched
  app/api/routes/weather.py, app/schemas/weather.py, app/services/weather_service.py,
  app/clients/openweather_client.py, frontend/**, requirements.txt
```

### Request flow

```
POST /api/v1/weather/insights
  → InsightService.advise(request)
      → WeatherService.forecast(lat, lon)      [existing, unchanged]
      → build_user_prompt(forecast…)           [fixed template + ≤40 point lines]
      → GeminiClient.generate_json(system, user, schema)
            15 s timeout → 504 · 429/401/403 → 503 · other HTTP/transport → 502
            non-JSON / no candidates → 502
      → WeatherAdvice.model_validate(raw)      [extra=forbid, 1–800 chars] → 502 on failure
  → InsightResponse(label=AI_LABEL, source=<from forecast>, + three sections)
```

## 4. Ordered tasks

| # | Task | Est. | Covers |
|---|---|---:|---|
| 1 | Write SPEC-002/PLAN-002 (this document) | done | — |
| 2 | `app/schemas/insight.py` + config keys + `.env.example` | 10 min | AI-FR-001, 007, 008, 011 |
| 3 | `insight_prompts.py` (instruction, template, response schema, prompt builder) | 15 min | AI-FR-004, 006 |
| 4 | `gemini_client.py` (call, header auth, error translation, JSON extraction) | 25 min | AI-FR-003, 008, AI-AC-003/004 |
| 5 | `insight_service.py` + `api/routes/insights.py` + `main.py` registration/CORS | 20 min | AI-FR-001/002/005, AI-AC-001/006 |
| 6 | Mocked tests (3 files) | 35 min | AI-AC-002…006, 008 |
| 7 | Run suite, secret-hygiene check, report | 15 min | AI-AC-007/008 |
| | **Total** | **~120 min** | |

## 5. Test list mapped to acceptance criteria

| Test file | Cases | AC |
|---|---|---|
| `tests/test_insights_routes.py` | 200 happy path (service mocked); 422 missing/invalid coordinates; `GeminiClientError(503)` → 503; `OpenWeatherClientError(404)` → 404; new path present in `/openapi.json`; existing endpoint tests untouched | AI-AC-001, 002, 007 |
| `tests/test_insight_service.py` | Prompt contains all point timestamps/values and no key; `label`/`source` server-set; missing/empty/overlong/extra field → `GeminiClientError(502)`; upstream forecast error propagates unchanged | AI-AC-005, 006 |
| `tests/test_gemini_client.py` | URL/model path, `x-goog-api-key` header, key absent from URL, JSON response config present; missing key → 503 with zero requests; timeout → 504; `429/401/500` → 503/503/502; non-JSON body → 502; empty candidates → 502 | AI-AC-003, 004, 008 |

All tests use `httpx.MockTransport` and a literal `"test-key"`; no live calls, no real key read.

## 6. Security, cost, reliability

- **Security:** key only via `SecretStr` environment, header auth, `extra="forbid"` schemas, safe `detail` strings, no provider payloads echoed. `.env` already git-ignored and absent from history (verified in review). Secret-hygiene grep run in task 7.
- **Cost:** one call/request, `maxOutputTokens` bounded, free-tier Flash model, upstream quota enforced by Google (≈5–15 RPM / ≈1,000–1,500 RPD) surfaced as `503`.
- **Reliability:** 15 s timeout, no retries; a Gemini outage degrades to an error message while all weather features keep working; CORS gains only `POST`.
- **Privacy:** city, country, 2-decimal coordinates, public forecast only.

## 7. Risks and assumptions

- **Provider access (discovered during testing):** the account's key returned `403 "Your project has been denied access"` for every model, including open Gemma models. No code or model-name change resolves this; the key/project must be fixed in Google AI Studio (create a fresh, unrestricted key). The app now maps `403` and `404` to `503` with actionable messages instead of the generic `502`.
- **Length caps vs. model verbosity:** an overlong section becomes `502` rather than truncated output; caps set at 800 chars with prompt guidance to stay short.
- **Pre-existing 5 test failures** remain (config `populate_by_name` issue), reported but not fixed in this task.
- **Untracked deployment surface:** Vercel environment must add `GEMINI_API_KEY` before the deployed app can use the feature (deployment config not changed here).

## 8. Rollback

All logic is in new files. Revert by removing the `insights_router` lines in `app/main.py` and deleting the new files; the config keys and `.env.example` lines are inert if unused. No existing endpoint contract changes, so no API consumer impact.

## 9. Stop point

Implement backend, run tests, report changed files/commands/results/blockers, and stop for review. Frontend, live Gemini verification, README updates, and any rate limiting await explicit approval.
