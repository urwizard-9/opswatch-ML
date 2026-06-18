"""OpsWatch 상태 점검 서비스.

등록된 서버에 HTTP GET 요청을 보내 UP/SLOW/DOWN 상태를 판별합니다.
"""

import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import get_logger
from app.models import CheckResult, Server
from app.routers.metrics import update_check_metrics, update_server_risk_metric
from app.services.incident_service import create_incident_if_needed
from app.services.risk_predictor import predict_realtime_server_risk

logger = get_logger(__name__)



async def check_server(url: str) -> dict:
    """단일 서버의 상태를 점검합니다."""
    try:
        start = time.time()
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=settings.CHECK_TIMEOUT_SECONDS)
        elapsed_ms = (time.time() - start) * 1000

        # 상태 판별
        if 200 <= response.status_code < 300:
            if elapsed_ms > settings.SLOW_THRESHOLD_SECONDS * 1000:
                status = "SLOW"
                message = f"응답 성공, 지연 발생 ({elapsed_ms:.0f}ms)"
            else:
                status = "UP"
                message = f"정상 응답 ({elapsed_ms:.0f}ms)"
        else:
            status = "DOWN"
            message = f"HTTP {response.status_code} 오류"

        result = {
            "status": status,
            "status_code": response.status_code,
            "response_time_ms": round(elapsed_ms, 2),
            "message": message,
        }
        logger.info(
            "SERVER_%s | url=%s | %dms | HTTP %d", status, url, elapsed_ms, response.status_code
        )
        update_check_metrics(status, result["response_time_ms"])
        return result

    except httpx.TimeoutException:
        logger.warning(
            "SERVER_DOWN | url=%s | Timeout (%d초 초과)", url, settings.CHECK_TIMEOUT_SECONDS
        )
        result = {
            "status": "DOWN",
            "status_code": None,
            "response_time_ms": None,
            "message": f"Timeout ({settings.CHECK_TIMEOUT_SECONDS}초 초과)",
        }
        update_check_metrics("DOWN", None)
        return result
    except httpx.ConnectError:
        logger.warning("SERVER_DOWN | url=%s | 연결 실패", url)
        result = {
            "status": "DOWN",
            "status_code": None,
            "response_time_ms": None,
            "message": "연결 실패 (서버 접근 불가)",
        }
        update_check_metrics("DOWN", None)
        return result
    except Exception as e:
        logger.exception("SERVER_CHECK_FAILED | url=%s | %s", url, e)
        result = {
            "status": "DOWN",
            "status_code": None,
            "response_time_ms": None,
            "message": f"점검 실패: {str(e)}",
        }
        update_check_metrics("DOWN", None)
        return result


async def run_monitoring_pipeline(db: Session, server: Server) -> dict:
    """단일 서버의 점검, DB 저장, 준실시간 AI 위험 예측 및 Incident 생성을 총괄하는 공통 파이프라인입니다."""
    # 1. 상태 점검 실행
    result = await check_server(server.url)
    now = datetime.now(timezone.utc)

    # 2. CheckResult 객체 생성 및 DB commit() 완료 (순서 정밀화: 예측 전에 이력 저장 완료)
    check_record = CheckResult(
        server_id=server.id,
        status=result["status"],
        status_code=result["status_code"],
        response_time_ms=result["response_time_ms"],
        message=result["message"],
        checked_at=now,
    )
    db.add(check_record)
    db.commit()

    # 3. 준실시간 AI 장애 예측 수행
    try:
        pred_res = predict_realtime_server_risk(db, server, result)
        risk_score = pred_res["risk_score"]
        is_down_pred = pred_res["is_down_pred"]

        # Prometheus 메트릭 갱신
        update_server_risk_metric(server.id, server.name, risk_score)

        # 로그 출력 (준실시간 로그 명칭 정정)
        logger.info(
            f"ML_SEMI_REALTIME_PREDICT | server_id={server.id} | name={server.name} | pred={is_down_pred} | risk={risk_score:.4f}"
        )

        if risk_score >= 0.8:
            logger.warning(
                f"ML_HIGH_RISK_DETECTED | server_id={server.id} | name={server.name} | risk={risk_score:.4f} | 장애 위험 임박"
            )
    except Exception as e:
        logger.warning(f"ML_SEMI_REALTIME_PREDICT_FAILED | server_id={server.id} | err={e}")

    # 4. DOWN 상태 시 Incident 자동 생성 (중복 방지 연동)
    if result["status"] == "DOWN":
        create_incident_if_needed(db, server.id, result["message"])

    return result

