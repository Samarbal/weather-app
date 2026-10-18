from datetime import datetime, timezone
from typing import Any

from app.clients.openweather_client import OpenWeatherClient
from app.schemas.weather import (
    CityMatch,
    CitySearchResponse,
    CurrentWeatherResponse,
    ForecastPoint,
    ForecastResponse,
    Location,
)


class WeatherService:
    def __init__(self, client: OpenWeatherClient | None = None) -> None:
        self.client = client or OpenWeatherClient()

    async def search_cities(self, query: str, limit: int = 5) -> CitySearchResponse:
        results = await self.client.search_cities(query, limit)
        cities = [
            CityMatch(
                name=item["name"],
                country=item["country"],
                state=item.get("state"),
                latitude=item["lat"],
                longitude=item["lon"],
            )
            for item in results
        ]
        return CitySearchResponse(query=query, results=cities)

    async def current_weather(self, latitude: float, longitude: float) -> CurrentWeatherResponse:
        data = await self.client.get_current_weather(latitude, longitude)
        return CurrentWeatherResponse(
            location=self._location(data),
            temperature_c=data["main"]["temp"],
            feels_like_c=data["main"]["feels_like"],
            humidity_percent=data["main"]["humidity"],
            wind_speed_kmh=data["wind"]["speed"] * 3.6,
            condition=data["weather"][0]["main"],
            description=data["weather"][0]["description"],
            observed_at=self._utc_timestamp(data["dt"]),
        )

    async def forecast(self, latitude: float, longitude: float) -> ForecastResponse:
        data = await self.client.get_forecast(latitude, longitude)
        city = data["city"]
        location = Location(
            name=city["name"],
            country=city["country"],
            latitude=city["coord"]["lat"],
            longitude=city["coord"]["lon"],
        )
        forecasts = [
            ForecastPoint(
                forecast_at=self._utc_timestamp(item["dt"]),
                feels_like_c=item["main"].get("feels_like"),
                temperature_c=item["main"]["temp"],
                humidity_percent=item["main"]["humidity"],
                wind_speed_kmh=item["wind"]["speed"] * 3.6,
                condition=item["weather"][0]["main"],
                description=item["weather"][0]["description"],
            )
            for item in data["list"]
        ]
        return ForecastResponse(
            location=location,
            timezone_offset_seconds=city.get("timezone"),
            items=forecasts,
        )

    @staticmethod
    def _location(data: dict[str, Any]) -> Location:
        return Location(
            name=data["name"],
            country=data["sys"]["country"],
            latitude=data["coord"]["lat"],
            longitude=data["coord"]["lon"],
        )

    @staticmethod
    def _utc_timestamp(value: int | float) -> datetime:
        return datetime.fromtimestamp(value, tz=timezone.utc)
