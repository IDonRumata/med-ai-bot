from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    telegram_bot_token: str
    allowed_user_id: int
    openai_api_key: str

    postgres_user: str = "medbot"
    postgres_password: str
    postgres_db: str = "medbot_db"
    postgres_host: str = "db"
    postgres_port: int = 5432

    encryption_key: str

    tz: str = "Europe/Minsk"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Cost optimization: use mini for simple tasks, full model for analysis
    openai_model_heavy: str = "gpt-4o"
    openai_model_light: str = "gpt-4o-mini"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
