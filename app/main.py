from fastapi import FastAPI

from app.api.routes.weather import router as weather_router

app = FastAPI(
    title="Weather App API",
    description="Backend API for the Weather App MVP.",
    version="0.1.0",
)
app.include_router(weather_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
