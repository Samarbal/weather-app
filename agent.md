# Weather App — Agent Instructions

## Product Goal and Current Phase

The overall product goal is a simple, clear Weather App for checking current conditions, a 3-hourly forecast, and a 5-day forecast. The current approved delivery phase is the backend MVP; frontend and Figma work are deferred, not removed from the overall product scope.

## Current Stack

- Backend: Python 3.11+ and FastAPI
- Validation and API schemas: Pydantic
- External weather provider: OpenWeather
- Interactive API documentation: Swagger UI at `/docs`
- Frontend: Deferred to a later phase
- Database: Not required

## Workflow

Follow this order:
1. Intent
2. Specification
3. Planning
4. Implementation
5. Testing
6. Review

For the current phase, prioritize the approved FastAPI backend requirements and Swagger-testable REST endpoints. Do not start frontend or Figma work until the backend phase is reviewed and approved.

## Rules

- Read the relevant project documents before making changes.
- Do not implement requirements that have not been approved.
- Work on one task at a time and stop at the requested task boundary.
- Keep changes small and focused; avoid unnecessary dependencies or infrastructure.
- Do not modify unrelated files.
- Ask for approval when requirements or architectural decisions are unclear.

## Backend Architecture

- FastAPI routes handle HTTP parameters, response models, and HTTP status mapping.
- Pydantic schemas define validated request and response contracts.
- Services contain weather use-case logic and response normalization.
- OpenWeather clients handle external HTTP communication.
- Keep `OPENWEATHER_API_KEY` server-side; never hardcode, print, return, or commit its value.
- Keep `.env` ignored by version control; commit no real credential.
- Avoid databases, deployment infrastructure, caching, and other nonessential services for the backend MVP.

## Future Frontend

When that phase is explicitly approved, implement the responsive web UI using the provided Figma designs. Preserve the product requirements for city search, user-initiated geolocation, English UI, Celsius temperatures, and km/h wind speeds. Do not treat the deferred frontend requirements as canceled.

## Verification and Reporting

After each implementation task:
- Run the smallest relevant validation.
- Report files changed, commands executed, results, and blockers.
- Do not claim tests passed unless they were run.
- Do not access, print, or disclose secret values during verification.

## Time Constraint

The current backend MVP has a 2-hour target. Prioritize a working, tested backend within the approved scope; report schedule risks rather than silently dropping requirements. Frontend work has a separate future estimate.

## Context and Token Efficiency

- Read only files directly relevant to the current task.
- Avoid rereading unchanged files within the same task.
- Use targeted file ranges instead of entire documents.
- Reuse existing project decisions and approved contracts.
- Invoke skills and documentation tools only when needed.
- Avoid repeated planning once implementation is approved.
- Prefer small, focused changes.
- Run relevant tests after implementation; rerun only when needed.
- Provide concise progress and final reports.
- Stop at the requested task boundary.