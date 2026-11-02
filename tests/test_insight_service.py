import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.clients.openai_client import OpenAIClientError
from app.clients.openweather_client import OpenWeatherClientError
from app.core.config import Settings
from app.schemas.insight import AI_LABEL, InsightRequest, InsightResponse
from app.schemas.weather import ForecastPoint, ForecastResponse, Location
from app.services.insight_prompts import INSIGHT_RESPONSE_SCHEMA, SYSTEM_INSTRUCTION
from app.services.insight_service import InsightService

VALID_ADVICE = {
    "weather_outlook": "Expect milder air midweek with showers by Thursday.",
    "what_to_wear": "A light jacket and a layer for the windier days.",
    "activity_tips": "Tuesday and Wednesday mornings look best for a long walk.",
}


def make_forecast() -> ForecastResponse:
    points = [
        ForecastPoint(
            forecast_at=datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc),
            temperature_c=14.5,
            feels_like_c=13.2,
            humidity_percent=72,
            condition="Clouds",
            description="broken clouds",
            wind_speed_kmh=11.5,
        ),
        ForecastPoint(
            forecast_at=datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc),
            temperature_c=9.8,
            feels_like_c=7.9,
            humidity_percent=88,
            condition="Rain",
            description="light rain",
            wind_speed_kmh=24.0,
        ),
        ForecastPoint(
            forecast_at=datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc),
            temperature_c=17.1,
            feels_like_c=17.0,
            humidity_percent=54,
            condition="Clear",
            description="clear sky",
            wind_speed_kmh=6.3,
        ),
    ]
    return ForecastResponse(
        location=Location(name="London", country="GB", latitude=51.51, longitude=-0.13),
        timezone_offset_seconds=0,
        items=points,
    )


class RecordingAIClient:
    """Duck-typed AI client double that records what was sent."""

    def __init__(self, payload: dict[str, Any] | Exception) -> None:
        self.payload = payload
        self.system_instruction: str | None = None
        self.user_prompt: str | None = None
        self.response_schema: dict[str, Any] | None = None

    async def generate_json(
        self, system_instruction: str, user_prompt: str, response_schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.system_instruction = system_instruction
        self.user_prompt = user_prompt
        self.response_schema = response_schema
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def make_service(
    ai_payload: dict[str, Any] | Exception | None = None,
    *,
    forecast: ForecastResponse | None = None,
) -> tuple[InsightService, RecordingAIClient, AsyncMock]:
    ai_client = RecordingAIClient(VALID_ADVICE if ai_payload is None else ai_payload)
    weather = AsyncMock()
    weather.forecast = AsyncMock(return_value=forecast or make_forecast())
    service = InsightService(weather_service=weather, ai_client=ai_client)  # type: ignore[arg-type]
    return service, ai_client, weather


def test_advise_returns_server_set_label_and_source() -> None:
    service, ai_client, weather = make_service()
    request = InsightRequest(latitude=51.51, longitude=-0.13, city_name="London", country="GB")

    response = asyncio.run(service.advise(request))

    assert isinstance(response, InsightResponse)
    assert response.label == AI_LABEL
    assert "AI-generated interpretation" in response.label
    assert response.weather_outlook == VALID_ADVICE["weather_outlook"]
    assert response.what_to_wear == VALID_ADVICE["what_to_wear"]
    assert response.activity_tips == VALID_ADVICE["activity_tips"]

    source = response.source
    assert source.city == "London"
    assert source.country == "GB"
    assert source.point_count == 3
    assert source.forecast_from == datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    assert source.forecast_to == datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)

    # The endpoint reuses the existing forecast pipeline with the caller's coordinates.
    weather.forecast.assert_awaited_once_with(51.51, -0.13)
    assert ai_client.system_instruction is not None
    assert "not a forecasting model" in ai_client.system_instruction
    assert ai_client.response_schema == INSIGHT_RESPONSE_SCHEMA


def test_prompt_contains_every_forecast_point_and_no_secrets() -> None:
    service, ai_client, _ = make_service()
    request = InsightRequest(latitude=51.51, longitude=-0.13, city_name="London")

    asyncio.run(service.advise(request))

    prompt = ai_client.user_prompt
    assert prompt is not None
    assert "London (GB)" in prompt
    assert "3 points" in prompt
    for point in make_forecast().items:
        assert point.forecast_at.isoformat(timespec="minutes") in prompt
        assert f"{round(point.temperature_c, 1)}C" in prompt
        assert f"{round(point.wind_speed_kmh, 1)} km/h" in prompt
        assert point.condition in prompt
        assert point.description in prompt
        assert f"{point.humidity_percent}%" in prompt
    # Grounding instructions travel with every request.
    assert SYSTEM_INSTRUCTION == ai_client.system_instruction
    assert "Never invent temperatures" in prompt or "Never invent temperatures" in SYSTEM_INSTRUCTION
    # No credential ever reaches the prompt.
    assert "test-key" not in prompt
    assert "OPENWEATHER" not in prompt


def test_prompt_converts_forecast_times_to_location_offset() -> None:
    forecast = make_forecast().model_copy(update={"timezone_offset_seconds": 7200})
    service, ai_client, _ = make_service(forecast=forecast)

    asyncio.run(service.advise(InsightRequest(latitude=51.51, longitude=-0.13)))

    assert ai_client.user_prompt is not None
    assert "2026-10-21T14:00+02:00" in ai_client.user_prompt
    assert "2026-10-23T14:00+02:00" in ai_client.user_prompt
    assert "2026-10-21T12:00+00:00" not in ai_client.user_prompt
    assert "in local time" in ai_client.user_prompt


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"weather_outlook": "Only one section."},
        {**VALID_ADVICE, "extra": "unexpected field"},
        {**VALID_ADVICE, "what_to_wear": ""},
        {**VALID_ADVICE, "activity_tips": "x" * 801},
        {**VALID_ADVICE, "weather_outlook": 42},
        {"weather_outlook": "", "what_to_wear": "", "activity_tips": ""},
    ],
)
def test_invalid_model_output_is_rejected_as_502(invalid_payload: dict[str, Any]) -> None:
    service, _, _ = make_service(ai_payload=invalid_payload)
    request = InsightRequest(latitude=51.51, longitude=-0.13)

    with pytest.raises(OpenAIClientError) as caught:
        asyncio.run(service.advise(request))

    assert caught.value.status_code == 502
    assert caught.value.code == "ai_invalid_model_response"


def test_provider_error_from_openai_passes_through_unchanged() -> None:
    upstream = OpenAIClientError(504, "ai_provider_timeout", "The AI service request timed out.")
    service, _, _ = make_service(ai_payload=upstream)
    request = InsightRequest(latitude=51.51, longitude=-0.13)

    with pytest.raises(OpenAIClientError) as caught:
        asyncio.run(service.advise(request))

    assert caught.value is upstream


def test_forecast_error_propagates_and_ai_is_never_called() -> None:
    upstream = OpenWeatherClientError(
        504, "weather_provider_timeout", "Weather provider request timed out."
    )
    weather = AsyncMock()
    weather.forecast = AsyncMock(side_effect=upstream)
    ai_client = RecordingAIClient(VALID_ADVICE)
    service = InsightService(weather_service=weather, ai_client=ai_client)  # type: ignore[arg-type]

    with pytest.raises(OpenWeatherClientError) as caught:
        asyncio.run(service.advise(InsightRequest(latitude=51.51, longitude=-0.13)))

    assert caught.value is upstream
    assert ai_client.system_instruction is None


def test_settings_declare_openai_configuration() -> None:
    assert Settings.model_fields["openai_api_key"].validation_alias == "OPENAI_API_KEY"
    model_field = Settings.model_fields["openai_model"]
    assert model_field.validation_alias == "OPENAI_MODEL"
    assert model_field.default == "gpt-6-luna"
