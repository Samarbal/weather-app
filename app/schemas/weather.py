from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WeatherResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Location(WeatherResponseModel):
    name: str
    country: str | None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class CityMatch(WeatherResponseModel):
    name: str
    state: str | None = None
    country: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class CitySearchResponse(WeatherResponseModel):
    query: str
    results: list[CityMatch]


class CurrentWeatherResponse(WeatherResponseModel):
    location: Location
    observed_at: datetime
    temperature_c: float
    feels_like_c: float
    humidity_percent: int = Field(ge=0, le=100)
    condition: str
    description: str
    wind_speed_kmh: float | None = Field(default=None, ge=0)


class ForecastPoint(WeatherResponseModel):
    forecast_at: datetime
    temperature_c: float
    feels_like_c: float | None = None
    humidity_percent: int | None = Field(default=None, ge=0, le=100)
    condition: str
    description: str
    wind_speed_kmh: float | None = Field(default=None, ge=0)


class ForecastResponse(WeatherResponseModel):
    location: Location
    timezone_offset_seconds: int | None = None
    items: list[ForecastPoint]
