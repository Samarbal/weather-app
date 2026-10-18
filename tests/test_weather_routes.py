from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.clients.openweather_client import OpenWeatherClientError
from app.main import app
from app.schemas.weather import CityMatch, CitySearchResponse

client = TestClient(app)


def test_search_cities_route() -> None:
    response_model = CitySearchResponse(
        query="London",
        results=[
            CityMatch(
                name="London",
                country="GB",
                latitude=51.5,
                longitude=-0.1,
            )
        ],
    )
    with patch("app.api.routes.weather.WeatherService") as service_class:
        service_class.return_value.search_cities = AsyncMock(return_value=response_model)

        response = client.get("/api/v1/cities/search", params={"q": "London"})

    assert response.status_code == 200
    assert response.json()["results"][0]["name"] == "London"


def test_current_weather_route_maps_provider_errors_safely() -> None:
    error = OpenWeatherClientError(504, "weather_provider_timeout", "Weather provider request timed out.")
    with patch("app.api.routes.weather.WeatherService") as service_class:
        service_class.return_value.current_weather = AsyncMock(side_effect=error)

        response = client.get(
            "/api/v1/weather/current",
            params={"lat": 51.5, "lon": -0.1},
        )

    assert response.status_code == 504
    assert response.json()["detail"] == "Weather provider request timed out."


def test_weather_routes_validate_coordinates() -> None:
    response = client.get("/api/v1/weather/current", params={"lat": 91, "lon": 0})

    assert response.status_code == 422


def test_weather_routes_are_in_openapi_schema() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/cities/search" in paths
    assert "/api/v1/weather/current" in paths
    assert "/api/v1/weather/forecast" in paths
