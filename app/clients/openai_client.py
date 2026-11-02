"""Server-side OpenAI Responses API client for weather insights."""

import json
import logging
from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings, get_settings

_URL = "https://api.openai.com/v1/responses"
_LOGGER = logging.getLogger(__name__)


class OpenAIClientError(Exception):
    """Safe provider error for translation by the API layer."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class OpenAIClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._explicit_key = api_key
        self._explicit_model = model
        self._settings = settings if settings is not None else get_settings()
        self._transport = transport

    async def generate_json(
        self,
        system_instruction: str,
        user_prompt: str,
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        settings = self._settings
        key = self._explicit_key if self._explicit_key is not None else (
            settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        )
        key = key.strip()
        if not key:
            raise OpenAIClientError(503, "ai_configuration_error", "The AI service is not configured.")

        body = {
            "model": self._explicit_model or settings.openai_model,
            "instructions": system_instruction,
            "input": user_prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "weather_advice",
                    "strict": True,
                    "schema": response_schema,
                }
            },
            "reasoning": {"effort": "none"},
            "max_output_tokens": 1200,
            "store": False,
        }

        started_at = perf_counter()
        outcome = "error"
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(settings.openai_timeout_seconds, connect=10.0),
            ) as client:
                response = await client.post(
                    _URL,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=body,
                )
                response.raise_for_status()
                outcome = "success"
        except httpx.TimeoutException:
            outcome = "timeout"
            raise OpenAIClientError(504, "ai_provider_timeout", "The AI service request timed out.") from None
        except httpx.HTTPStatusError as error:
            outcome = "http_error"
            raise self._status_error(error.response.status_code) from None
        except httpx.RequestError:
            outcome = "request_error"
            raise OpenAIClientError(502, "ai_provider_error", "The AI service could not be reached.") from None
        finally:
            log = _LOGGER.warning if outcome == "timeout" else _LOGGER.info
            log("OpenAI HTTP request outcome=%s elapsed_seconds=%.3f", outcome, perf_counter() - started_at)

        return self._parse_content(response)

    @staticmethod
    def _status_error(status_code: int) -> OpenAIClientError:
        if status_code == 429:
            return OpenAIClientError(503, "ai_provider_rate_limited", "The AI service is temporarily unavailable. Please try again later.")
        if status_code in (401, 403):
            return OpenAIClientError(503, "ai_configuration_error", "The AI service access was denied. Check your OpenAI project and API key.")
        if status_code == 402:
            return OpenAIClientError(503, "ai_configuration_error", "The AI service billing is not available.")
        if status_code == 404:
            return OpenAIClientError(503, "ai_configuration_error", "The configured AI model is unavailable. Update OPENAI_MODEL.")
        return OpenAIClientError(502, "ai_provider_error", "The AI service returned an unexpected response.")

    @staticmethod
    def _parse_content(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            raise OpenAIClientError(502, "ai_invalid_response", "The AI service returned an unreadable response.") from None
        if not isinstance(payload, dict):
            raise OpenAIClientError(502, "ai_invalid_response", "The AI service returned an unreadable response.")

        status = payload.get("status")
        safe_status = status if status in ("completed", "incomplete", "failed") else "unknown"
        usage = payload.get("usage")
        safe_usage = {
            field: value for field in ("input_tokens", "output_tokens", "total_tokens")
            if isinstance(usage, dict)
            and isinstance(value := usage.get(field), int)
            and not isinstance(value, bool)
            and value >= 0
        }
        _LOGGER.info("OpenAI response status=%s token_usage=%s", safe_status, safe_usage)
        if status != "completed":
            reason = payload.get("incomplete_details")
            if isinstance(reason, dict) and reason.get("reason") == "max_output_tokens":
                raise OpenAIClientError(502, "ai_output_truncated", "The AI response could not be understood.")
            raise OpenAIClientError(502, "ai_invalid_response", "The AI service returned an unreadable response.")

        output = payload.get("output")
        if not isinstance(output, list):
            raise OpenAIClientError(502, "ai_invalid_response", "The AI service returned an unreadable response.")
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            contents = item.get("content")
            if not isinstance(contents, list):
                continue
            for content in contents:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text = content.get("text")
                    if isinstance(text, str):
                        try:
                            parsed = json.loads(text)
                        except ValueError:
                            break
                        if isinstance(parsed, dict):
                            return parsed
        raise OpenAIClientError(502, "ai_invalid_response", "The AI response could not be understood.")
