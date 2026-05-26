from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "StateProof"
    debug: bool = False
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]

    database_url: str = "postgresql+asyncpg://stateproof:stateproof@localhost:5432/stateproof"

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30


settings = Settings()
