from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    openweather_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENWEATHER_API_KEY",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
