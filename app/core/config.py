from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        # Allow field-name construction (tests/SDK); environment variables keep
        # using the OPENWEATHER_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY aliases.
        populate_by_name=True,
    )

    openweather_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENWEATHER_API_KEY",
    )

    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="GEMINI_API_KEY",
    )

    gemini_model: str = Field(
        default="gemini-3.8-flash",
        validation_alias="GEMINI_MODEL",
    )

    gemini_timeout_seconds: float = Field(
        default=45.0,
        gt=0,
        le=300,
        validation_alias="GEMINI_TIMEOUT_SECONDS",
    )

    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )
    openai_model: str = Field(
        default="gpt-6-luna",
        validation_alias="OPENAI_MODEL",
    )
    openai_timeout_seconds: float = Field(
        default=45.0,
        gt=0,
        le=300,
        validation_alias="OPENAI_TIMEOUT_SECONDS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
