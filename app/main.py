from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.weather import router as weather_router

app = FastAPI(
    title="Weather App API",
    description="Backend API for the Weather App MVP.",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://frontend-one-rust-bm8y3mcx02.vercel.app",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(weather_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
