"""OpsWatch 상태 점검 서비스.

등록된 서버에 HTTP GET 요청을 보내 UP/SLOW/DOWN 상태를 판별합니다.
"""

import time

import httpx

from app.config import settings
from app.logging_config import get_logger
from app.routers.metrics import update_check_metrics

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
