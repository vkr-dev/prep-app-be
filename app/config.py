from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM ---
    anthropic_api_key: str
    # Default is Sonnet 5, not Opus: this is a personal project where every
    # generation call is real spend, and Sonnet is cheap enough here to be a
    # non-issue while staying plenty capable for structured Q&A generation.
    # Bump to "claude-opus-5" any time by changing this one value.
    anthropic_model: str = "claude-sonnet-5"

    # --- Auth ---
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    # This is only the identity token's own lifetime, not the access window -
    # the guard dependency re-checks status + access_expires_at in the DB on
    # every request, so a long-lived JWT here does not extend guest access.
    jwt_expire_minutes: int = 60 * 24
    guest_access_window_hours: int = 1

    owner_email: str
    owner_password_hash: str

    # --- DB ---
    database_url: str

    # --- CORS ---
    cors_allow_origins: str = "http://localhost:4200"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


settings = Settings()
