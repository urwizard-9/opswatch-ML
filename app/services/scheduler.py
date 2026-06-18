"""OpsWatch 백그라운드 스케줄러.

앱 시작 시 asyncio 태스크로 실행되어
CHECK_INTERVAL_SECONDS 주기로 활성 서버 전체를 자동 점검합니다.
"""

import asyncio

from app.config import settings
from app.database import SessionLocal
from app.logging_config import get_logger
from app.models import Incident, Server
from app.routers.metrics import update_gauge_from_results, update_incident_gauge
from app.services.monitor_service import run_monitoring_pipeline

logger = get_logger(__name__)


async def run_scheduled_checks() -> None:
    """주기적으로 활성 서버 전체를 자동 점검하는 루프입니다."""
    logger.info(
        "SCHEDULER_STARTED | interval=%ds",
        settings.CHECK_INTERVAL_SECONDS,
    )

    while True:
        await asyncio.sleep(settings.CHECK_INTERVAL_SECONDS)

        db = SessionLocal()
        try:
            servers = db.query(Server).filter(Server.is_active == True).all()  # noqa: E712
            if not servers:
                logger.info("SCHEDULER_SKIP | 활성 서버 없음")
                continue

            logger.info("SCHEDULER_RUN | 점검 대상 %d대", len(servers))

            results = []

            for server in servers:
                # 공통 모니터링 파이프라인 수행 (점검 ➔ 저장 ➔ 준실시간 AI 추론 ➔ 메트릭 ➔ Incident 생성)
                result = await run_monitoring_pipeline(db, server)
                results.append(result)

            # 게이지 메트릭 갱신
            update_gauge_from_results(results)
            open_count = db.query(Incident).filter(Incident.status == "OPEN").count()
            update_incident_gauge(open_count)

            up = sum(1 for r in results if r["status"] == "UP")
            slow = sum(1 for r in results if r["status"] == "SLOW")
            down = sum(1 for r in results if r["status"] == "DOWN")
            logger.info(
                "SCHEDULER_DONE | total=%d | UP=%d | SLOW=%d | DOWN=%d",
                len(results),
                up,
                slow,
                down,
            )

        except Exception:
            logger.exception("SCHEDULER_ERROR | 스케줄러 실행 중 예외 발생")
        finally:
            db.close()

