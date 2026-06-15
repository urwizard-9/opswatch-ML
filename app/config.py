"""OpsWatch 설정 관리 모듈."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정.

    환경변수 또는 .env 파일에서 값을 읽어옵니다.
    """

    # 애플리케이션
    APP_NAME: str = "OpsWatch"
    APP_VERSION: str = "1.0.0"

    # 데이터베이스
    DATABASE_URL: str = "sqlite:///./opswatch.db"

    # 로깅
    LOG_LEVEL: str = "INFO"

    # 상태 점검 설정
    CHECK_TIMEOUT_SECONDS: int = 5
    SLOW_THRESHOLD_SECONDS: int = 2
    CHECK_INTERVAL_SECONDS: int = 60

    # GitHub Issue 자동 생성
    ENABLE_GITHUB_ISSUE: bool = False
    GH_REPO: str = ""
    GH_TOKEN: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
