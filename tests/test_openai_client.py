import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from app.clients.openai_client import OpenAIClient, OpenAIClientError
from app.core.config import Settings
from app.services.insight_prompts import INSIGHT_RESPONSE_SCHEMA

ADVICE = {
    "weather_outlook": "Warm afternoons with a chance of rain later.",
    "what_to_wear": "Wear light layers.",
    "activity_tips": "Plan outdoor time for the morning.",
}


def run_async(result: Awaitable[Any]) -> Any:
    return asyncio.run(result)


def response_payload(text: str, status: str = "completed") -> dict[str, Any]:
    return {
        "status": status,
        "output": [
            {"type": "reasoning", "content": []},
            {"type": "message", "content": [{"type": "output_text", "text": text}]},
        ],
        "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
    }


def make_client(
    handler: Callable[[httpx.Request], Awaitable[httpx.Response]],
    *,
    api_key: str = "test-key",
    timeout_seconds: float = 45,
) -> OpenAIClient:
    return OpenAIClient(
        api_key=api_key,
        settings=Settings(_env_file=None, openai_timeout_seconds=timeout_seconds),
        transport=httpx.MockTransport(handler),
    )


def generate(client: OpenAIClient) -> dict[str, Any]:
    return run_async(client.generate_json("Private rules", "Private forecast", INSIGHT_RESPONSE_SCHEMA))


def test_sends_server_side_key_and_structured_schema(caplog: pytest.LogCaptureFixture) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=response_payload(json.dumps(ADVICE)))

    with caplog.at_level("INFO", logger="app.clients.openai_client"):
        assert generate(make_client(handler)) == ADVICE

    request = requests[0]
    body = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == "https://api.openai.com/v1/responses"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert body["model"] == "gpt-6-luna"
    assert body["instructions"] == "Private rules"
    assert body["input"] == "Private forecast"
    assert body["store"] is False
    assert body["reasoning"] == {"effort": "none"}
    assert body["text"]["format"] == {
        "type": "json_schema",
        "name": "weather_advice",
        "strict": True,
        "schema": INSIGHT_RESPONSE_SCHEMA,
    }
    assert request.extensions["timeout"]["read"] == 45.0
    assert "outcome=success" in caplog.text
    assert "status=completed" in caplog.text
    for private_text in ("test-key", "Private rules", "Private forecast", ADVICE["weather_outlook"]):
        assert private_text not in caplog.text


def test_missing_key_fails_before_request() -> None:
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=response_payload(json.dumps(ADVICE)))

    with pytest.raises(OpenAIClientError) as caught:
        generate(make_client(handler, api_key="  "))

    assert caught.value.status_code == 503
    assert caught.value.code == "ai_configuration_error"
    assert calls == []


@pytest.mark.parametrize("status", [401, 403, 429])
def test_provider_errors_are_sanitized(status: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "secret test-key provider text"}})

    with pytest.raises(OpenAIClientError) as caught:
        generate(make_client(handler))

    assert caught.value.status_code == 503
    assert "test-key" not in caught.value.message
    assert "secret" not in caught.value.message


def test_timeout_keeps_existing_504_contract(caplog: pytest.LogCaptureFixture) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private provider text")

    with caplog.at_level("WARNING", logger="app.clients.openai_client"):
        with pytest.raises(OpenAIClientError) as caught:
            generate(make_client(handler))

    assert caught.value.status_code == 504
    assert caught.value.message == "The AI service request timed out."
    assert "outcome=timeout" in caplog.text
    assert "private provider text" not in caplog.text


def test_incomplete_response_is_rejected() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = response_payload('{"weather_outlook":', status="incomplete")
        payload["incomplete_details"] = {"reason": "max_output_tokens"}
        return httpx.Response(200, json=payload)

    with pytest.raises(OpenAIClientError) as caught:
        generate(make_client(handler))

    assert caught.value.status_code == 502
    assert caught.value.code == "ai_output_truncated"


def test_refusal_and_malformed_json_are_rejected() -> None:
    async def refusal(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "No."}]}],
        })

    async def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_payload('{"weather_outlook":'))

    for handler in (refusal, malformed):
        with pytest.raises(OpenAIClientError) as caught:
            generate(make_client(handler))
        assert caught.value.status_code == 502
