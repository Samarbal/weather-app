import math
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.config import Settings, get_settings

_BASE_URL = "https://api.openweathermap.org"
_GEOCODING_PATH = "/geo/1.0/direct"
_CURRENT_PATH = "/data/2.5/weather"
_FORECAST_PATH = "/data/2.5/forecast"
_TIMEOUT_SECONDS = 10.0


class OpenWeatherClientError(Exception):
    """Safe provider error for translation by the API layer."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class OpenWeatherClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings if settings is not None else get_settings()
        self._transport = transport

    async def search_cities(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        payload = await self._get_json(
            _GEOCODING_PATH,
            {"q": query, "limit": limit},
        )
        if not isinstance(payload, list):
            raise self._invalid_response()
        for city in payload:
            self._validate_city_match(city)
        return payload

    async def get_current_weather(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        payload = await self._get_json(
            _CURRENT_PATH,
            {"lat": latitude, "lon": longitude, "units": "metric", "lang": "en"},
            location_not_found=True,
        )
        self._validate_current_weather(payload)
        return payload

    async def get_forecast(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        payload = await self._get_json(
            _FORECAST_PATH,
            {"lat": latitude, "lon": longitude, "units": "metric", "lang": "en"},
            location_not_found=True,
        )
        self._validate_forecast(payload)
        return payload

    async def _get_json(
        self,
        path: str,
        params: dict[str, str | int | float],
        *,
        location_not_found: bool = False,
    ) -> Any:
        api_key = self._api_key()
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(_TIMEOUT_SECONDS),
            ) as client:
                response = await client.get(
                    f"{_BASE_URL}{path}",
                    params={**params, "appid": api_key},
                )
                response.raise_for_status()
        except httpx.TimeoutException:
            raise OpenWeatherClientError(
                504, "weather_provider_timeout", "Weather provider request timed out."
            ) from None
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            if status_code == 404 and location_not_found:
                raise OpenWeatherClientError(
                    404, "location_not_found", "Weather location was not found."
                ) from None
            if status_code == 429:
                raise OpenWeatherClientError(
                    503,
                    "weather_provider_rate_limited",
                    "Weather provider is temporarily unavailable.",
                ) from None
            raise OpenWeatherClientError(
                502,
                "weather_provider_error",
                "Weather provider request failed.",
            ) from None
        except httpx.RequestError:
            raise OpenWeatherClientError(
                502,
                "weather_provider_error",
                "Weather provider request failed.",
            ) from None

        try:
            return response.json()
        except ValueError:
            raise self._invalid_response() from None

    def _api_key(self) -> str:
        configured_key = self._settings.openweather_api_key
        if configured_key is None:
            raise OpenWeatherClientError(
                503,
                "weather_configuration_error",
                "Weather provider is not configured.",
            )
        api_key = configured_key.get_secret_value().strip()
        if not api_key:
            raise OpenWeatherClientError(
                503,
                "weather_configuration_error",
                "Weather provider is not configured.",
            )
        return api_key

    @classmethod
    def _validate_city_match(cls, city: Any) -> None:
        if not isinstance(city, Mapping):
            raise cls._invalid_response()
        cls._require_text(city.get("name"))
        cls._require_text(city.get("country"))
        cls._require_coordinate(city.get("lat"), -90, 90)
        cls._require_coordinate(city.get("lon"), -180, 180)
        state = city.get("state")
        if state is not None and not isinstance(state, str):
            raise cls._invalid_response()

    @classmethod
    def _validate_current_weather(cls, payload: Any) -> None:
        if not isinstance(payload, Mapping):
            raise cls._invalid_response()
        cls._require_text(payload.get("name"))
        cls._validate_coordinates(payload.get("coord"))
        cls._validate_country(payload.get("sys"))
        cls._validate_main(
            payload.get("main"), require_feels_like=True, require_humidity=True
        )
        cls._validate_condition(payload.get("weather"))
        cls._require_number(payload.get("dt"))
        cls._validate_wind(payload.get("wind"))

    @classmethod
    def _validate_forecast(cls, payload: Any) -> None:
        if not isinstance(payload, Mapping):
            raise cls._invalid_response()
        city = payload.get("city")
        if not isinstance(city, Mapping):
            raise cls._invalid_response()
        cls._require_text(city.get("name"))
        cls._validate_coordinates(city.get("coord"))
        cls._validate_country(city)

        timezone = city.get("timezone")
        if timezone is not None and (
            isinstance(timezone, bool) or not isinstance(timezone, int)
        ):
            raise cls._invalid_response()

        forecast_items = payload.get("list")
        if (
            not isinstance(forecast_items, list)
            or not forecast_items
            or len(forecast_items) > 40
        ):
            raise cls._invalid_response()
        for item in forecast_items:
            if not isinstance(item, Mapping):
                raise cls._invalid_response()
            cls._require_number(item.get("dt"))
            cls._validate_main(
                item.get("main"), require_feels_like=False, require_humidity=False
            )
            cls._validate_condition(item.get("weather"))
            cls._validate_wind(item.get("wind"))

    @classmethod
    def _validate_coordinates(cls, coordinates: Any) -> None:
        if not isinstance(coordinates, Mapping):
            raise cls._invalid_response()
        cls._require_coordinate(coordinates.get("lat"), -90, 90)
        cls._require_coordinate(coordinates.get("lon"), -180, 180)

    @classmethod
    def _validate_country(cls, parent: Any) -> None:
        if parent is None:
            return
        if not isinstance(parent, Mapping):
            raise cls._invalid_response()
        country = parent.get("country")
        if country is not None and not isinstance(country, str):
            raise cls._invalid_response()

    @classmethod
    def _validate_main(
        cls,
        main: Any,
        *,
        require_feels_like: bool,
        require_humidity: bool,
    ) -> None:
        if not isinstance(main, Mapping):
            raise cls._invalid_response()
        cls._require_number(main.get("temp"))
        feels_like = main.get("feels_like")
        if require_feels_like or feels_like is not None:
            cls._require_number(feels_like)
        humidity = main.get("humidity")
        if require_humidity or humidity is not None:
            cls._require_percentage(humidity)

    @classmethod
    def _validate_condition(cls, weather: Any) -> None:
        if not isinstance(weather, list) or not weather:
            raise cls._invalid_response()
        condition = weather[0]
        if not isinstance(condition, Mapping):
            raise cls._invalid_response()
        cls._require_text(condition.get("main"))
        cls._require_text(condition.get("description"))

    @classmethod
    def _validate_wind(cls, wind: Any) -> None:
        if wind is None:
            return
        if not isinstance(wind, Mapping):
            raise cls._invalid_response()
        speed = wind.get("speed")
        if speed is not None and cls._require_number(speed) < 0:
            raise cls._invalid_response()

    @classmethod
    def _require_coordinate(cls, value: Any, minimum: float, maximum: float) -> float:
        number = cls._require_number(value)
        if not minimum <= number <= maximum:
            raise cls._invalid_response()
        return number

    @classmethod
    def _require_percentage(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise cls._invalid_response()
        if not 0 <= value <= 100:
            raise cls._invalid_response()
        return value

    @classmethod
    def _require_number(cls, value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise cls._invalid_response()
        try:
            number = float(value)
        except (OverflowError, ValueError):
            raise cls._invalid_response() from None
        if not math.isfinite(number):
            raise cls._invalid_response()
        return number

    @classmethod
    def _require_text(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise cls._invalid_response()
        return value

    @staticmethod
    def _invalid_response() -> OpenWeatherClientError:
        return OpenWeatherClientError(
            502,
            "weather_provider_invalid_response",
            "Weather provider returned an invalid response.",
        )
