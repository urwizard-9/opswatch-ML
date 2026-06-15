"""OpsWatch 백그라운드 스케줄러.

앱 시작 시 asyncio 태스크로 실행되어
CHECK_INTERVAL_SECONDS 주기로 활성 서버 전체를 자동 점검합니다.
"""

import asyncio
from datetime import datetime, timezone

from app.config import settings
from app.database import SessionLocal
from app.logging_config import get_logger
from app.models import Incident, Server
from app.routers.metrics import update_gauge_from_results, update_incident_gauge
from app.services.incident_service import create_incident_if_needed
from app.services.monitor_service import check_server

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

            from app.models import CheckResult

            results = []
            now = datetime.now(timezone.utc)

            for server in servers:
                result = await check_server(server.url)
                results.append(result)

                # DB에 점검 결과 저장
                check_record = CheckResult(
                    server_id=server.id,
                    status=result["status"],
                    status_code=result["status_code"],
                    response_time_ms=result["response_time_ms"],
                    message=result["message"],
                    checked_at=now,
                )
                db.add(check_record)

                # DOWN이면 Incident 자동 생성
                if result["status"] == "DOWN":
                    create_incident_if_needed(db, server.id, result["message"])

            db.commit()

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
