"""pytest 공통 설정 및 픽스처.

인메모리 SQLite는 연결마다 독립적이므로,
StaticPool을 사용하여 모든 연결이 같은 인메모리 DB를 공유하게 합니다.
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import StaticPool, create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

# ── StaticPool: 모든 연결이 동일한 인메모리 DB를 공유 ──
engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

import app.database as _db  # noqa: E402

_db.engine = engine_test
_db.SessionLocal = TestingSessionLocal

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


def override_get_db():
    """테스트용 DB 세션 오버라이드."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """각 테스트 전 테이블 생성, 후 삭제 (격리 보장)."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture()
def client(setup_db):
    """FastAPI TestClient (DB 세션 오버라이드 포함)."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
