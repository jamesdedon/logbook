from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_path: str = "/data/logbook.db"
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_prefix": "LOGBOOK_"}

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"


settings = Settings()
