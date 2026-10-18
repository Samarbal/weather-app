from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.weather_service import WeatherService


@pytest.mark.anyio
async def test_current_weather_normalizes_wind_speed_and_timestamp() -> None:
    client = AsyncMock()
    client.get_current_weather.return_value = {
        "name": "London",
        "coord": {"lat": 51.5, "lon": -0.1},
        "sys": {"country": "GB"},
        "main": {"temp": 12.0, "feels_like": 11.0, "humidity": 70},
        "wind": {"speed": 5.0},
        "weather": [{"main": "Clouds", "description": "overcast clouds"}],
        "dt": 1_700_000_000,
    }

    result = await WeatherService(client).current_weather(51.5, -0.1)

    assert result.wind_speed_kmh == pytest.approx(18.0)
    assert result.observed_at == datetime.fromtimestamp(1_700_000_000, timezone.utc)
    client.get_current_weather.assert_awaited_once_with(51.5, -0.1)


@pytest.mark.anyio
async def test_forecast_normalizes_all_provider_points() -> None:
    client = AsyncMock()
    client.get_forecast.return_value = {
        "city": {
            "name": "London",
            "country": "GB",
            "coord": {"lat": 51.5, "lon": -0.1},
            "timezone": 0,
        },
        "list": [
            {
                "dt": 1_700_000_000,
                "main": {"temp": 12.0, "humidity": 70},
                "wind": {"speed": 5.0},
                "weather": [{"main": "Clouds", "description": "cloudy"}],
            }
        ],
    }

    result = await WeatherService(client).forecast(51.5, -0.1)

    assert len(result.items) == 1
    assert result.items[0].wind_speed_kmh == pytest.approx(18.0)
    assert result.items[0].forecast_at.tzinfo == timezone.utc


@pytest.mark.anyio
async def test_city_search_maps_provider_locations() -> None:
    client = AsyncMock()
    client.search_cities.return_value = [
        {"name": "London", "country": "GB", "state": "England", "lat": 51.5, "lon": -0.1}
    ]

    result = await WeatherService(client).search_cities("London", 5)

    assert result.results[0].name == "London"
    assert result.results[0].country == "GB"
