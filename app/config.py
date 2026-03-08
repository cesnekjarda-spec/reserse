from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Reserse"
    app_env: str = "development"
    base_url: str = "http://127.0.0.1:8000"
    database_url: str = "sqlite:///./app.db"
    session_cookie_name: str = "research_session"
    sync_secret: str = "dev-sync-secret"

    bootstrap_admin_username: str = "Admin"
    bootstrap_admin_email: str = "admin@example.local"
    bootstrap_admin_password: str = "Ahojky12345"

    bootstrap_user_username: str = "User"
    bootstrap_user_email: str = "user@example.local"
    bootstrap_user_password: str = "Ahojky54321"

    auto_seed_on_startup: bool = True
    auto_sync_on_startup: bool = False
    brief_article_limit: int = 18
    brief_fetch_limit: int = 5
    article_fetch_timeout_seconds: int = 12

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


settings = Settings()
