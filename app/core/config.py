from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = "AI Culinary Assistant"
    debug: bool = False
    version: str = "0.1.0"

    # Security
    secret_key: str

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )


settings = Settings()
