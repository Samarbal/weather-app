import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from app.clients.gemini_client import GeminiClient, GeminiClientError
from app.core.config import Settings


def run_async(result: Awaitable[Any]) -> Any:
    return asyncio.run(result)


def gemini_payload(text: str) -> dict[str, Any]:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def make_client(
    handler: Callable[[httpx.Request], Awaitable[httpx.Response]],
    *,
    api_key: str | None = "test-key",
    model: str | None = "test-model",
) -> GeminiClient:
    return GeminiClient(
        api_key=api_key,
        model=model,
        transport=httpx.MockTransport(handler),
    )


def test_generate_json_sends_header_auth_and_structured_config() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=gemini_payload('{"weather_outlook": "ok"}'))

    result = run_async(
        make_client(handler).generate_json(
            "System rules here.", "Forecast prompt here.", {"type": "OBJECT"}
        )
    )

    assert result == {"weather_outlook": "ok"}
    assert len(requests) == 1
    request = requests[0]

    assert request.method == "POST"
    assert request.url.path == "/v1beta/models/test-model:generateContent"
    # The key travels in a header, never in the URL.
    assert "test-key" not in str(request.url)
    assert request.headers["x-goog-api-key"] == "test-key"

    body = request.content
    assert b"System rules here." in body
    assert b"Forecast prompt here." in body
    config = json.loads(body)["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseSchema"] == {"type": "OBJECT"}
    assert config["maxOutputTokens"] == 2048


def test_gemini_request_uses_configured_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.clients.gemini_client.get_settings",
        lambda: Settings(_env_file=None, gemini_timeout_seconds=30),
    )
    timeouts: list[dict[str, float]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        timeouts.append(request.extensions["timeout"])
        return httpx.Response(200, json=gemini_payload("{}"))

    run_async(make_client(handler).generate_json("s", "u", {"type": "OBJECT"}))

    assert timeouts == [{"connect": 30.0, "read": 30.0, "write": 30.0, "pool": 30.0}]


def test_valid_structured_response_logs_only_safe_metadata(caplog: pytest.LogCaptureFixture) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"weather_outlook":"sunny"}'}]}}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "thoughtsTokenCount": 10, "totalTokenCount": 130},
        })

    with caplog.at_level("INFO", logger="app.clients.gemini_client"):
        result = run_async(make_client(handler).generate_json("private prompt", "private forecast", {"type": "OBJECT"}))

    assert result == {"weather_outlook": "sunny"}
    assert "finish_reason=STOP" in caplog.text
    assert "outcome=success timeout_phase=none elapsed_seconds=" in caplog.text
    assert "promptTokenCount" in caplog.text
    assert "private prompt" not in caplog.text
    assert "private forecast" not in caplog.text
    assert "sunny" not in caplog.text
    assert "test-key" not in caplog.text


def test_default_model_uses_supported_low_thinking_level() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=gemini_payload('{}'))

    run_async(make_client(handler, model="gemini-3.8-flash").generate_json("s", "u", {"type": "OBJECT"}))

    config = json.loads(requests[0].content)["generationConfig"]
    assert config["thinkingConfig"] == {"thinkingLevel": "LOW"}


def test_max_tokens_is_classified_before_parsing_truncated_json(caplog: pytest.LogCaptureFixture) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": '{"weather_outlook":'}]}}],
            "usageMetadata": {"thoughtsTokenCount": 2048},
        })

    with caplog.at_level("INFO", logger="app.clients.gemini_client"):
        with pytest.raises(GeminiClientError) as caught:
            run_async(make_client(handler).generate_json("secret prompt", "forecast data", {"type": "OBJECT"}))

    assert caught.value.status_code == 502
    assert caught.value.code == "ai_output_truncated"
    assert "finish_reason=MAX_TOKENS" in caplog.text
    assert "forecast data" not in caplog.text
    assert "weather_outlook" not in caplog.text


def test_truncated_json_with_stop_still_returns_safe_502() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"weather_outlook":'}]}}],
        })

    with pytest.raises(GeminiClientError) as caught:
        run_async(make_client(handler).generate_json("s", "u", {"type": "OBJECT"}))

    assert caught.value.status_code == 502
    assert caught.value.code == "ai_invalid_response"


def test_blank_api_key_fails_before_any_request() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=gemini_payload("{}"))

    with pytest.raises(GeminiClientError) as caught:
        run_async(
            make_client(handler, api_key="   ").generate_json("s", "u", {"type": "OBJECT"})
        )

    assert caught.value.status_code == 503
    assert caught.value.code == "ai_configuration_error"
    assert requests == []


@pytest.mark.parametrize(
    ("upstream_status", "expected_status", "expected_code"),
    [
        (429, 503, "ai_provider_rate_limited"),
        (401, 503, "ai_configuration_error"),
        (403, 503, "ai_configuration_error"),
        (400, 502, "ai_provider_error"),
        (500, 502, "ai_provider_error"),
    ],
)
def test_upstream_statuses_map_to_safe_errors(
    upstream_status: int, expected_status: int, expected_code: str
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            upstream_status,
            json={"error": {"message": "raw provider detail with test-key inside"}},
        )

    with pytest.raises(GeminiClientError) as caught:
        run_async(make_client(handler).generate_json("s", "u", {"type": "OBJECT"}))

    assert caught.value.status_code == expected_status
    assert caught.value.code == expected_code
    assert "test-key" not in caught.value.message
    assert "raw provider detail" not in caught.value.message


def test_timeout_maps_to_504_and_logs_elapsed_time_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ticks = iter((10.0, 12.5))
    monkeypatch.setattr("app.clients.gemini_client.perf_counter", lambda: next(ticks))

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret provider detail")

    with caplog.at_level("INFO", logger="app.clients.gemini_client"):
        with pytest.raises(GeminiClientError) as caught:
            run_async(make_client(handler).generate_json("private prompt", "private forecast", {"type": "OBJECT"}))

    assert caught.value.status_code == 504
    assert caught.value.code == "ai_provider_timeout"
    assert "outcome=timeout timeout_phase=read elapsed_seconds=2.500" in caplog.text
    assert "private prompt" not in caplog.text
    assert "private forecast" not in caplog.text
    assert "secret provider detail" not in caplog.text
    assert "test-key" not in caplog.text


def test_connect_timeout_is_identified_without_logging_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("private connection detail")

    with caplog.at_level("WARNING", logger="app.clients.gemini_client"):
        with pytest.raises(GeminiClientError) as caught:
            run_async(make_client(handler).generate_json("s", "u", {"type": "OBJECT"}))

    assert caught.value.status_code == 504
    assert "outcome=timeout timeout_phase=connect" in caplog.text
    assert "private connection detail" not in caplog.text


def test_connection_error_maps_to_502() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    with pytest.raises(GeminiClientError) as caught:
        run_async(make_client(handler).generate_json("s", "u", {"type": "OBJECT"}))

    assert caught.value.status_code == 502
    assert caught.value.code == "ai_provider_error"


def test_non_json_body_maps_to_502() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    with pytest.raises(GeminiClientError) as caught:
        run_async(make_client(handler).generate_json("s", "u", {"type": "OBJECT"}))

    assert caught.value.status_code == 502
    assert caught.value.code == "ai_invalid_response"


@pytest.mark.parametrize(
    "text",
    [
        "this is not json at all",
        '["a", "list", "instead"]',
    ],
)
def test_unusable_candidate_text_maps_to_502(text: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=gemini_payload(text))

    with pytest.raises(GeminiClientError) as caught:
        run_async(make_client(handler).generate_json("s", "u", {"type": "OBJECT"}))

    assert caught.value.status_code == 502
    assert caught.value.code == "ai_invalid_response"


def test_missing_candidates_maps_to_502() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    with pytest.raises(GeminiClientError) as caught:
        run_async(make_client(handler).generate_json("s", "u", {"type": "OBJECT"}))

    assert caught.value.status_code == 502
    assert caught.value.code == "ai_invalid_response"
