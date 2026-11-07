from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _to_psycopg(url: str) -> str:
    """Neon이 주는 postgresql:// 주소를 SQLAlchemy psycopg3 드라이버 주소로 바꾼다."""
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    # psycopg는 channel_binding 파라미터를 그대로 받는다. 추가 처리 없음.
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    database_url_unpooled: str = ""
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_hours: int = 24 * 7
    # 배포(https)에서는 true. 로컬 http 개발에서는 false여야 쿠키가 저장된다.
    cookie_secure: bool = False
    max_upload_mb: int = 30

    @property
    def db_url(self) -> str:
        return _to_psycopg(self.database_url)

    @property
    def migration_db_url(self) -> str:
        return _to_psycopg(self.database_url_unpooled or self.database_url)


settings = Settings()
