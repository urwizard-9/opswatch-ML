"""OpsWatch FastAPI 애플리케이션 진입점."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import app.database as _db
from app.config import settings
from app.database import Base
from app.logging_config import get_logger, setup_logging
from app.routers import checks, incidents, metrics, ml, mock_targets, servers
from app.schemas import HealthResponse
from app.services.model_loader import load_champion_model
from app.services.scheduler import run_scheduled_checks

# 로깅 초기화
setup_logging()
logger = get_logger(__name__)
logger.info("APP_STARTED | %s v%s", settings.APP_NAME, settings.APP_VERSION)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 lifespan 이벤트."""
    # DB 테이블 생성 (테스트 시 _db.engine이 교체되면 테스트 엔진에 생성됨)
    Base.metadata.create_all(bind=_db.engine)
    # ML Champion 모델 동적 로드
    try:
        load_champion_model()
    except Exception as e:
        logger.error("APP_LIFESPAN_ML_LOAD_FAILED | err=%s", e)
    # 백그라운드 스케줄러 등록
    task = asyncio.create_task(run_scheduled_checks())
    logger.info("SCHEDULER_REGISTERED | interval=%ds", settings.CHECK_INTERVAL_SECONDS)
    yield
    # 종료: 스케줄러 정리
    task.cancel()
    logger.info("APP_SHUTDOWN")


# FastAPI 인스턴스 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="배포 서버 통신 상태 모니터링 및 장애 이력관리 시스템",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic 입력값 검증 오류 발생 시 상세 내용을 WARNING 로그로 기록합니다."""
    errors = exc.errors()
    err_msgs = []
    for err in errors:
        loc = " -> ".join(str(loc_val) for loc_val in err.get("loc", []))
        msg = err.get("msg", "unknown error")
        err_msgs.append(f"{loc}: {msg}")

    joined_msg = " | ".join(err_msgs)
    logger.warning(
        "VALIDATION_FAILED | endpoint=%s | error=%s", request.url.path, joined_msg
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )

# 라우터 등록
app.include_router(servers.router)
app.include_router(mock_targets.router)
app.include_router(checks.router)
app.include_router(incidents.router)
app.include_router(metrics.router)
app.include_router(ml.router)


@app.get("/health", response_model=HealthResponse, tags=["Operation"])
def health_check():
    """OpsWatch 앱 자체 상태 확인.

    GitHub Actions smoke test 및 Render 배포 확인용.
    """
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME.lower(),
        version=settings.APP_VERSION,
    )
