from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

AI_LABEL = (
    "AI-generated interpretation of the OpenWeather 5-day forecast "
    "— not an independent weather prediction."
)

MAX_SECTION_LENGTH = 800


class InsightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    city_name: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, min_length=0, max_length=2)


class InsightSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str
    country: str | None
    forecast_from: datetime
    forecast_to: datetime
    point_count: int = Field(ge=1, le=40)


class WeatherAdvice(BaseModel):
    """The three sections produced by the model; server-set fields live outside it."""

    model_config = ConfigDict(extra="forbid")

    weather_outlook: str = Field(min_length=1, max_length=MAX_SECTION_LENGTH)
    what_to_wear: str = Field(min_length=1, max_length=MAX_SECTION_LENGTH)
    activity_tips: str = Field(min_length=1, max_length=MAX_SECTION_LENGTH)


class InsightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    source: InsightSource
    weather_outlook: str = Field(min_length=1, max_length=MAX_SECTION_LENGTH)
    what_to_wear: str = Field(min_length=1, max_length=MAX_SECTION_LENGTH)
    activity_tips: str = Field(min_length=1, max_length=MAX_SECTION_LENGTH)
