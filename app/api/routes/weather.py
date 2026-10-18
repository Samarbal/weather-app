from fastapi import APIRouter, HTTPException, Query
from typing import NoReturn

from app.clients.openweather_client import OpenWeatherClientError
from app.schemas.weather import CitySearchResponse, CurrentWeatherResponse, ForecastResponse
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/api/v1", tags=["weather"])


def _raise_http_error(error: OpenWeatherClientError) -> NoReturn:
    raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/cities/search", response_model=CitySearchResponse)
async def search_cities(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(5, ge=1, le=5),
) -> CitySearchResponse:
    query = q.strip()
    if not 2 <= len(query) <= 100:
        raise HTTPException(status_code=422, detail="Query must contain 2 to 100 characters.")
    try:
        return await WeatherService().search_cities(query, limit)
    except OpenWeatherClientError as error:
        _raise_http_error(error)


@router.get("/weather/current", response_model=CurrentWeatherResponse)
async def current_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> CurrentWeatherResponse:
    try:
        return await WeatherService().current_weather(lat, lon)
    except OpenWeatherClientError as error:
        _raise_http_error(error)


@router.get("/weather/forecast", response_model=ForecastResponse)
async def forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> ForecastResponse:
    try:
        return await WeatherService().forecast(lat, lon)
    except OpenWeatherClientError as error:
        _raise_http_error(error)
