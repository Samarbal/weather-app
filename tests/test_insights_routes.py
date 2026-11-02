from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.clients.openai_client import OpenAIClientError
from app.clients.openweather_client import OpenWeatherClientError
from app.main import app
from app.schemas.insight import AI_LABEL, InsightResponse, InsightSource

client = TestClient(app)

VALID_BODY = {"latitude": 51.51, "longitude": -0.13, "city_name": "London", "country": "GB"}


def make_response() -> InsightResponse:
    return InsightResponse(
        label=AI_LABEL,
        source=InsightSource(
            city="London",
            country="GB",
            forecast_from="2026-10-21T12:00:00Z",
            forecast_to="2026-10-23T12:00:00Z",
            point_count=3,
        ),
        weather_outlook="Cooler and windier midweek.",
        what_to_wear="Bring a jacket.",
        activity_tips="Tuesday morning is the driest window.",
    )


def test_insights_endpoint_returns_advice() -> None:
    with patch("app.api.routes.insights.InsightService") as service_class:
        service_class.return_value.advise = AsyncMock(return_value=make_response())

        response = client.post("/api/v1/weather/insights", json=VALID_BODY)

    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] == AI_LABEL
    assert payload["source"]["city"] == "London"
    assert payload["source"]["point_count"] == 3
    assert set(payload) == {
        "label",
        "source",
        "weather_outlook",
        "what_to_wear",
        "activity_tips",
    }
    assert "AI-generated interpretation" in payload["label"]


def test_insights_endpoint_validates_coordinates_without_calling_services() -> None:
    with patch("app.api.routes.insights.InsightService") as service_class:
        missing = client.post("/api/v1/weather/insights", json={"latitude": 51.5})
        out_of_range = client.post(
            "/api/v1/weather/insights", json={"latitude": 91, "longitude": 0}
        )

    assert missing.status_code == 422
    assert out_of_range.status_code == 422
    service_class.return_value.advise.assert_not_called()


def test_insights_endpoint_rejects_unknown_body_fields() -> None:
    with patch("app.api.routes.insights.InsightService") as service_class:
        response = client.post(
            "/api/v1/weather/insights", json={**VALID_BODY, "units": "imperial"}
        )

    assert response.status_code == 422
    service_class.return_value.advise.assert_not_called()


def test_missing_ai_configuration_returns_503_safely() -> None:
    error = OpenAIClientError(
        503, "ai_configuration_error", "The AI service is not configured."
    )
    with patch("app.api.routes.insights.InsightService") as service_class:
        service_class.return_value.advise = AsyncMock(side_effect=error)

        response = client.post("/api/v1/weather/insights", json=VALID_BODY)

    assert response.status_code == 503
    assert response.json()["detail"] == "The AI service is not configured."
    assert "key" not in response.json()["detail"].lower()


def test_ai_rate_limit_returns_503() -> None:
    error = OpenAIClientError(
        503,
        "ai_provider_rate_limited",
        "The AI service is temporarily unavailable. Please try again later.",
    )
    with patch("app.api.routes.insights.InsightService") as service_class:
        service_class.return_value.advise = AsyncMock(side_effect=error)

        response = client.post("/api/v1/weather/insights", json=VALID_BODY)

    assert response.status_code == 503


def test_invalid_model_response_returns_502() -> None:
    error = OpenAIClientError(
        502, "ai_invalid_model_response", "The AI response could not be understood."
    )
    with patch("app.api.routes.insights.InsightService") as service_class:
        service_class.return_value.advise = AsyncMock(side_effect=error)

        response = client.post("/api/v1/weather/insights", json=VALID_BODY)

    assert response.status_code == 502
    assert response.json()["detail"] == "The AI response could not be understood."


def test_forecast_location_error_propagates_unchanged() -> None:
    error = OpenWeatherClientError(404, "location_not_found", "Weather location was not found.")
    with patch("app.api.routes.insights.InsightService") as service_class:
        service_class.return_value.advise = AsyncMock(side_effect=error)

        response = client.post("/api/v1/weather/insights", json=VALID_BODY)

    assert response.status_code == 404
    assert response.json()["detail"] == "Weather location was not found."


def test_insights_endpoint_is_documented_in_openapi() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/weather/insights" in paths
    assert "post" in paths["/api/v1/weather/insights"]


def test_existing_endpoints_are_unchanged() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/api/v1/cities/search"]) == {"get"}
    assert set(paths["/api/v1/weather/current"]) == {"get"}
    assert set(paths["/api/v1/weather/forecast"]) == {"get"}
