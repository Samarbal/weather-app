from fastapi import APIRouter, HTTPException, status

from app.clients.openai_client import OpenAIClientError
from app.clients.openweather_client import OpenWeatherClientError
from app.schemas.insight import InsightRequest, InsightResponse
from app.services.insight_service import InsightService

router = APIRouter(prefix="/api/v1", tags=["weather"])


@router.post(
    "/weather/insights",
    response_model=InsightResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Weather location not found."},
        422: {"description": "Invalid request body."},
        502: {"description": "AI provider failure or invalid AI response."},
        503: {"description": "AI provider not configured or rate limited."},
        504: {"description": "Upstream request timed out."},
    },
)
async def weather_insights(request: InsightRequest) -> InsightResponse:
    try:
        return await InsightService().advise(request)
    except (OpenWeatherClientError, OpenAIClientError) as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
