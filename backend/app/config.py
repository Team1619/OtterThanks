from pathlib import Path
from typing import Any, List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OtterThanks"

    # PostgreSQL Database Credentials
    postgres_user: str = "otter"
    postgres_password: str = "otterpass"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "otterthanks"
    database_url: Optional[str] = None

    static_dist_dir: str = str(
        Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    )
    cors_origins: List[str] = ["*"]

    # Google Workspace OAuth & Group Authorization
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: Optional[str] = None
    allowed_google_group: Optional[str] = None  # e.g. mentors@team1619.net
    allowed_mentor_emails: Optional[str] = None  # Comma-separated list of mentor emails allowed access

    # Session & Security
    session_secret_key: str = "otterthanks-secure-session-key-change-in-production"
    session_cookie_name: str = "otterthanks_session"
    session_expire_hours: int = 168  # 7 days
    dev_mode: bool = False

    # Slack Bot Integration
    slack_bot_token: Optional[str] = None  # e.g. xoxb-...
    slack_channel_id: Optional[str] = None  # Public kudos channel ID
    slack_mentor_channel_id: Optional[str] = None  # Private mentor review channel ID
    slack_signing_secret: Optional[str] = None  # Slack app signing secret for request verification

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )


settings = Settings()
