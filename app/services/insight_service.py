from pydantic import ValidationError

from app.clients.openai_client import OpenAIClient, OpenAIClientError
from app.schemas.insight import (
    AI_LABEL,
    InsightRequest,
    InsightResponse,
    InsightSource,
    WeatherAdvice,
)
from app.schemas.weather import ForecastResponse
from app.services.insight_prompts import (
    INSIGHT_RESPONSE_SCHEMA,
    SYSTEM_INSTRUCTION,
    build_user_prompt,
)
from app.services.weather_service import WeatherService


class InsightService:
    def __init__(
        self,
        weather_service: WeatherService | None = None,
        ai_client: OpenAIClient | None = None,
    ) -> None:
        self.weather_service = weather_service or WeatherService()
        self.ai_client = ai_client or OpenAIClient()

    async def advise(self, request: InsightRequest) -> InsightResponse:
        # Reuse the existing forecast pipeline: the model only interprets
        # weather data the app itself fetched from OpenWeather.
        forecast = await self.weather_service.forecast(request.latitude, request.longitude)

        raw = await self.ai_client.generate_json(
            SYSTEM_INSTRUCTION,
            build_user_prompt(forecast, request.city_name),
            INSIGHT_RESPONSE_SCHEMA,
        )

        try:
            advice = WeatherAdvice.model_validate(raw)
        except ValidationError:
            raise OpenAIClientError(
                502,
                "ai_invalid_model_response",
                "The AI response could not be understood.",
            ) from None

        return InsightResponse(
            label=AI_LABEL,
            source=self._source(forecast, request),
            **advice.model_dump(),
        )

    @staticmethod
    def _source(forecast: ForecastResponse, request: InsightRequest) -> InsightSource:
        first = forecast.items[0]
        last = forecast.items[-1]
        return InsightSource(
            city=request.city_name or forecast.location.name,
            country=forecast.location.country or request.country,
            forecast_from=first.forecast_at,
            forecast_to=last.forecast_at,
            point_count=len(forecast.items),
        )
