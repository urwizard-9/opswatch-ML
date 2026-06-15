"""OpsWatch 데이터베이스 설정 모듈."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# SQLAlchemy 엔진 생성
# SQLite의 경우 check_same_thread=False 필요
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base 클래스 (SQLAlchemy 2.x 스타일)
class Base(DeclarativeBase):
    """모든 ORM 모델의 기본 클래스."""

    pass


def get_db():
    """FastAPI Dependency: DB 세션을 제공하고 요청 종료 시 닫습니다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
