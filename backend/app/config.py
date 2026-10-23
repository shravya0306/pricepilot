from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


PRODUCTION_FRONTEND_ORIGIN = "https://pricepilot-lime-theta.vercel.app"


class Settings(BaseSettings):
    gemini_api_key: str = ""
    serper_api_key: str = ""
    scraper_api_key: str = ""
    gemini_model: str = "models/gemini-2.5-flash-lite"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173,"
        f"{PRODUCTION_FRONTEND_ORIGIN}"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]
        if PRODUCTION_FRONTEND_ORIGIN not in origins:
            origins.append(PRODUCTION_FRONTEND_ORIGIN)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
