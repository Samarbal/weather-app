"""Regression tests for Settings construction (no real secrets, no .env reads)."""

from pydantic import SecretStr

from app.core.config import Settings


def test_explicit_field_name_value_overrides_environment() -> None:
    """Field-name construction must win; previously validation_alias swallowed it
    and tests silently received the developer's real key from .env."""
    settings = Settings(_env_file=None, openweather_api_key=SecretStr("unit-test-key"))

    assert settings.openweather_api_key is not None
    assert settings.openweather_api_key.get_secret_value() == "unit-test-key"


def test_environment_alias_still_populates(monkeypatch) -> None:
    monkeypatch.setenv("OPENWEATHER_API_KEY", "env-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")

    settings = Settings(_env_file=None)

    assert settings.openweather_api_key is not None
    assert settings.openweather_api_key.get_secret_value() == "env-test-key"
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "env-gemini-key"
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "env-openai-key"


def test_missing_configuration_stays_none(monkeypatch) -> None:
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.openweather_api_key is None
    assert settings.gemini_api_key is None
    assert settings.gemini_model == "gemini-3.8-flash"
    assert settings.gemini_timeout_seconds == 45.0
    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-6-luna"
    assert settings.openai_timeout_seconds == 45.0


def test_gemini_timeout_can_be_configured(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "30")

    settings = Settings(_env_file=None)

    assert settings.gemini_timeout_seconds == 30.0
