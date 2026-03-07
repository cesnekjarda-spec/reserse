from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Research Feed App"
    app_env: str = "development"
    database_url: str
    session_cookie_name: str = "research_session"
    sync_secret: str = "change-me"
    admin_email: str | None = None
    admin_password: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


settings = Settings()
