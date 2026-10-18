import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.clients.openweather_client import (
    OpenWeatherClient,
    OpenWeatherClientError,
)
from app.core.config import Settings
from app.schemas.weather import (
    CitySearchResponse,
    CurrentWeatherResponse,
    ForecastResponse,
)


def run_async(result: Awaitable[Any]) -> Any:
    return asyncio.run(result)


def make_settings(api_key: str | None = "test-key") -> Settings:
    return Settings(
        openweather_api_key=SecretStr(api_key) if api_key is not None else None
    )


def make_client(
    handler: Callable[[httpx.Request], Awaitable[httpx.Response]],
    *,
    api_key: str | None = "test-key",
) -> OpenWeatherClient:
    return OpenWeatherClient(
        settings=make_settings(api_key),
        transport=httpx.MockTransport(handler),
    )


def test_city_search_uses_geocoding_endpoint_and_expected_parameters() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "name": "London",
                    "state": "England",
                    "country": "GB",
                    "lat": 51.5072,
                    "lon": -0.1276,
                }
            ],
        )

    result = run_async(make_client(handler).search_cities("London", limit=3))

    assert result[0]["name"] == "London"
    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == "/geo/1.0/direct"
    assert request.url.params["q"] == "London"
    assert request.url.params["limit"] == "3"
    assert request.url.params["appid"] == "test-key"
    assert set(request.url.params) == {"q", "limit", "appid"}


def test_city_search_accepts_no_matches() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    assert run_async(make_client(handler).search_cities("Unknown")) == []


@pytest.mark.parametrize(
    ("method_name", "path", "expected_params", "payload"),
    [
        (
            "get_current_weather",
            "/data/2.5/weather",
            {"lat": "51.5", "lon": "-0.1", "units": "metric", "lang": "en"},
            {
                "name": "London",
                "coord": {"lat": 51.5, "lon": -0.1},
                "sys": {"country": "GB"},
                "dt": 1700000000,
                "main": {
                    "temp": 12,
                    "feels_like": 10,
                    "humidity": 70,
                },
                "weather": [{"main": "Clouds", "description": "broken clouds"}],
                "wind": {"speed": 2.5},
            },
        ),
        (
            "get_forecast",
            "/data/2.5/forecast",
            {"lat": "51.5", "lon": "-0.1", "units": "metric", "lang": "en"},
            {
                "city": {
                    "name": "London",
                    "country": "GB",
                    "coord": {"lat": 51.5, "lon": -0.1},
                    "timezone": 0,
                },
                "list": [
                    {
                        "dt": 1700000000,
                        "main": {"temp": 12, "feels_like": 10, "humidity": 70},
                        "weather": [{"main": "Clouds", "description": "broken clouds"}],
                        "wind": {"speed": 2.5},
                    }
                ],
            },
        ),
    ],
)
def test_weather_calls_use_expected_endpoint_and_parameters(
    method_name: str,
    path: str,
    expected_params: dict[str, str],
    payload: dict[str, Any],
) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    client = make_client(handler)
    method = getattr(client, method_name)
    result = run_async(method(51.5, -0.1))

    assert result == payload
    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == path
    assert {key: request.url.params[key] for key in expected_params} == expected_params
    assert request.url.params["appid"] == "test-key"
    assert "cnt" not in request.url.params


@pytest.mark.parametrize("api_key", [None, "   "])
def test_missing_or_blank_api_key_fails_before_making_request(
    api_key: str | None,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("A request must not be sent without configuration.")

    client = make_client(handler, api_key=api_key)

    with pytest.raises(OpenWeatherClientError) as error:
        run_async(client.search_cities("London"))

    assert error.value.status_code == 503
    assert error.value.code == "weather_configuration_error"
    assert "test-key" not in str(error.value)


@pytest.mark.parametrize(
    ("provider_status", "expected_status", "expected_code"),
    [
        (401, 502, "weather_provider_error"),
        (429, 503, "weather_provider_rate_limited"),
        (500, 502, "weather_provider_error"),
        (404, 404, "location_not_found"),
    ],
)
def test_provider_statuses_are_translated_without_provider_body(
    provider_status: int, expected_status: int, expected_code: str
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            provider_status,
            text="provider detail includes test-key",
        )

    client = make_client(handler)

    with pytest.raises(OpenWeatherClientError) as error:
        run_async(client.get_current_weather(51.5, -0.1))

    assert error.value.status_code == expected_status
    assert error.value.code == expected_code
    assert "test-key" not in str(error.value)
    assert "provider detail" not in str(error.value)


def test_city_search_provider_404_is_an_upstream_error_not_no_matches() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    with pytest.raises(OpenWeatherClientError) as error:
        run_async(make_client(handler).search_cities("London"))

    assert error.value.status_code == 502
    assert error.value.code == "weather_provider_error"


def test_timeout_is_translated_to_safe_gateway_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("request included test-key", request=request)

    with pytest.raises(OpenWeatherClientError) as error:
        run_async(make_client(handler).get_forecast(51.5, -0.1))

    assert error.value.status_code == 504
    assert error.value.code == "weather_provider_timeout"
    assert "test-key" not in str(error.value)


def test_malformed_json_is_translated_to_bad_gateway() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="{invalid json")

    with pytest.raises(OpenWeatherClientError) as error:
        run_async(make_client(handler).search_cities("London"))

    assert error.value.status_code == 502
    assert error.value.code == "weather_provider_invalid_response"


@pytest.mark.parametrize(
    ("method_name", "payload"),
    [
        ("search_cities", {"not": "a list"}),
        ("get_current_weather", {"name": "London"}),
        ("get_current_weather", {"sys": "invalid"}),
        (
            "get_current_weather",
            {
                "name": "London",
                "coord": {"lat": 51.5, "lon": -0.1},
                "sys": {"country": "GB"},
                "dt": 1700000000,
                "main": {"temp": 12, "feels_like": 10},
                "weather": [{"main": "Clouds", "description": "broken clouds"}],
            },
        ),
        (
            "get_forecast",
            {
                "city": {"name": "London", "coord": {"lat": 51.5, "lon": -0.1}},
                "list": [],
            },
        ),
    ],
)
def test_malformed_provider_shape_is_not_returned_as_success(
    method_name: str, payload: Any
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = make_client(handler)
    method = getattr(client, method_name)
    arguments = ("London",) if method_name == "search_cities" else (51.5, -0.1)

    with pytest.raises(OpenWeatherClientError) as error:
        run_async(method(*arguments))

    assert error.value.status_code == 502
    assert error.value.code == "weather_provider_invalid_response"


def test_response_schemas_match_approved_contracts() -> None:
    city_response = CitySearchResponse(
        query="London",
        results=[
            {
                "name": "London",
                "country": "GB",
                "latitude": 51.5,
                "longitude": -0.1,
            }
        ],
    )
    current_response = CurrentWeatherResponse(
        location={
            "name": "London",
            "country": "GB",
            "latitude": 51.5,
            "longitude": -0.1,
        },
        observed_at="2026-10-17T00:00:00Z",
        temperature_c=12,
        feels_like_c=10,
        humidity_percent=70,
        condition="Clouds",
        description="broken clouds",
        wind_speed_kmh=9,
    )
    forecast_response = ForecastResponse(
        location={
            "name": "London",
            "country": "GB",
            "latitude": 51.5,
            "longitude": -0.1,
        },
        timezone_offset_seconds=0,
        items=[
            {
                "forecast_at": "2026-10-17T03:00:00Z",
                "temperature_c": 12,
                "feels_like_c": 10,
                "humidity_percent": 70,
                "condition": "Clouds",
                "description": "broken clouds",
                "wind_speed_kmh": 9,
            }
        ],
    )

    assert city_response.results[0].state is None
    assert current_response.observed_at.tzinfo is not None
    assert forecast_response.items[0].temperature_c == 12
