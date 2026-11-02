import json
import logging
from time import perf_counter
from typing import Any

import httpx

from app.core.config import get_settings

_BASE_URL = "https://generativelanguage.googleapis.com"
_LOGGER = logging.getLogger(__name__)
_USAGE_FIELDS = (
    "promptTokenCount",
    "candidatesTokenCount",
    "thoughtsTokenCount",
    "totalTokenCount",
)


class GeminiClientError(Exception):
    """Safe AI-provider error for translation by the API layer."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class GeminiClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._explicit_key = api_key
        self._explicit_model = model
        self._transport = transport

    async def generate_json(
        self,
        system_instruction: str,
        user_prompt: str,
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        api_key = self._api_key()
        model = self._model()
        generation_config = {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
            "maxOutputTokens": 2048,
        }
        if model == "gemini-3.8-flash":
            generation_config["thinkingConfig"] = {"thinkingLevel": "LOW"}
        else:
            generation_config["temperature"] = 0.3
        body = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": generation_config,
        }

        started_at = perf_counter()
        outcome = "error"
        timeout_phase = "none"
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(get_settings().gemini_timeout_seconds),
            ) as client:
                response = await client.post(
                    f"{_BASE_URL}/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json=body,
                )
                response.raise_for_status()
                outcome = "success"
        except httpx.TimeoutException as error:
            outcome = "timeout"
            timeout_phase = {
                httpx.ConnectTimeout: "connect",
                httpx.ReadTimeout: "read",
                httpx.WriteTimeout: "write",
                httpx.PoolTimeout: "pool",
            }.get(type(error), "unknown")
            raise GeminiClientError(
                504, "ai_provider_timeout", "The AI service request timed out."
            ) from None
        except httpx.HTTPStatusError as error:
            outcome = "http_error"
            raise self._status_error(error.response.status_code) from None
        except httpx.RequestError:
            outcome = "request_error"
            raise GeminiClientError(
                502, "ai_provider_error", "The AI service could not be reached."
            ) from None
        finally:
            log = _LOGGER.warning if outcome == "timeout" else _LOGGER.info
            log(
                "Gemini HTTP request outcome=%s timeout_phase=%s elapsed_seconds=%.3f",
                outcome,
                timeout_phase,
                perf_counter() - started_at,
            )

        return self._parse_content(response)

    def _api_key(self) -> str:
        if self._explicit_key is None:
            configured = get_settings().gemini_api_key
            api_key = "" if configured is None else configured.get_secret_value().strip()
        else:
            api_key = self._explicit_key.strip()
        if not api_key:
            raise GeminiClientError(
                503,
                "ai_configuration_error",
                "The AI service is not configured.",
            )
        return api_key

    def _model(self) -> str:
        if self._explicit_model:
            return self._explicit_model
        return get_settings().gemini_model

    @staticmethod
    def _status_error(status_code: int) -> GeminiClientError:
        if status_code == 429:
            return GeminiClientError(
                503,
                "ai_provider_rate_limited",
                "The AI service is temporarily unavailable. Please try again later.",
            )
        if status_code in (401, 403):
            return GeminiClientError(
                503,
                "ai_configuration_error",
                "The AI service access was denied. Check your Google Cloud project and API key.",
            )
        if status_code == 404:
            return GeminiClientError(
                503,
                "ai_configuration_error",
                "The configured AI model is unavailable. Update GEMINI_MODEL.",
            )
        return GeminiClientError(
            502,
            "ai_provider_error",
            "The AI service returned an unexpected response.",
        )

    @staticmethod
    def _parse_content(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            raise GeminiClientError(
                502, "ai_invalid_response", "The AI service returned an unreadable response."
            ) from None

        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        candidate = candidates[0] if isinstance(candidates, list) and candidates else {}
        reason = candidate.get("finishReason") if isinstance(candidate, dict) else None
        safe_reason = reason if isinstance(reason, str) and reason in {
            "STOP", "MAX_TOKENS", "SAFETY", "RECITATION", "LANGUAGE",
            "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII",
            "MALFORMED_FUNCTION_CALL", "IMAGE_SAFETY",
        } else "UNKNOWN"
        usage = payload.get("usageMetadata", {}) if isinstance(payload, dict) else {}
        safe_usage = {
            field: value for field in _USAGE_FIELDS
            if isinstance(usage, dict)
            and isinstance(value := usage.get(field), int)
            and not isinstance(value, bool)
            and value >= 0
        }
        _LOGGER.info("Gemini finish_reason=%s token_usage=%s", safe_reason, safe_usage)
        if safe_reason == "MAX_TOKENS":
            raise GeminiClientError(
                502, "ai_output_truncated", "The AI response could not be understood."
            )
        if safe_reason not in ("STOP", "UNKNOWN"):
            raise GeminiClientError(
                502, "ai_invalid_response", "The AI service returned an unreadable response."
            )

        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise GeminiClientError(
                502, "ai_invalid_response", "The AI service returned an unreadable response."
            ) from None
        if not isinstance(text, str):
            raise GeminiClientError(
                502, "ai_invalid_response", "The AI service returned an unreadable response."
            )

        try:
            parsed = json.loads(text)
        except ValueError:
            raise GeminiClientError(
                502, "ai_invalid_response", "The AI response could not be understood."
            ) from None
        if not isinstance(parsed, dict):
            raise GeminiClientError(
                502, "ai_invalid_response", "The AI response could not be understood."
            )
        return parsed
