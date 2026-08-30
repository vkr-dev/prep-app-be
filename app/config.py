from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM ---
    # "1" = Anthropic, "2" = Google - selects which app/llm/*_client.py
    # implements call_structured() for every pipeline step. See
    # app/llm/client.py. Swap providers with this one setting, no code change.
    llm_provider: str = "1"

    # Only the active provider's key needs to actually be set - both default
    # to empty so an unused provider never blocks startup.
    anthropic_api_key: str = ""
    # Default is Sonnet 5, not Opus: this is a personal project where every
    # generation call is real spend, and Sonnet is cheap enough here to be a
    # non-issue while staying plenty capable for structured Q&A generation.
    # Bump to "claude-opus-5" any time by changing this one value.
    anthropic_model: str = "claude-sonnet-5"

    google_api_key: str = ""
    # Google AI Studio's free tier - the cheap/free swap-in slot from context.md.
    google_model: str = "gemini-3.6-flash"

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
