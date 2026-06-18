"""OpsWatch Prometheus 메트릭 라우터.

/metrics 엔드포인트에서 Prometheus가 스크레이프할 수 있는
텍스트 포맷의 메트릭을 노출합니다.
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest

router = APIRouter(tags=["Metrics"])

# ── 카운터: 누적 점검 횟수 ──
checks_total = Counter(
    "opswatch_checks_total",
    "총 상태 점검 횟수",
    ["status"],  # UP / SLOW / DOWN
)

# ── 게이지: 현재 상태별 서버 수 ──
servers_up = Gauge("opswatch_servers_up", "현재 UP 상태 서버 수")
servers_slow = Gauge("opswatch_servers_slow", "현재 SLOW 상태 서버 수")
servers_down = Gauge("opswatch_servers_down", "현재 DOWN 상태 서버 수")

# ── 게이지: 현재 OPEN 장애 수 ──
incidents_open = Gauge("opswatch_incidents_open", "현재 OPEN 상태 Incident 수")

# ── 게이지: 서버별 실시간 AI 장애 위험 점수 ──
server_risk_score = Gauge(
    "opswatch_server_risk_score",
    "서버별 실시간 AI 장애 위험 점수 (0.0 ~ 1.0)",
    ["server_id", "server_name"],
)

# ── 히스토그램: 응답 시간 분포 ──
response_time_histogram = Histogram(
    "opswatch_response_time_ms",
    "서버 응답 시간 (ms)",
    buckets=[50, 100, 200, 500, 1000, 2000, 5000],
)


@router.get("/metrics", response_class=PlainTextResponse)
def get_metrics():
    """Prometheus 메트릭을 텍스트 포맷으로 반환합니다."""
    return generate_latest()


def update_check_metrics(status: str, response_time_ms: float | None) -> None:
    """점검 결과에 따라 메트릭을 업데이트합니다.

    Args:
        status: UP, SLOW, DOWN 중 하나
        response_time_ms: 응답 시간 (ms). None이면 히스토그램 기록 안 함.
    """
    checks_total.labels(status=status).inc()

    if response_time_ms is not None:
        response_time_histogram.observe(response_time_ms)


def update_gauge_from_results(results: list[dict]) -> None:
    """전체 점검 결과로 게이지 메트릭을 갱신합니다.

    Args:
        results: check_server 반환값 리스트
    """
    up = sum(1 for r in results if r["status"] == "UP")
    slow = sum(1 for r in results if r["status"] == "SLOW")
    down = sum(1 for r in results if r["status"] == "DOWN")
    servers_up.set(up)
    servers_slow.set(slow)
    servers_down.set(down)


def update_incident_gauge(open_count: int) -> None:
    """현재 OPEN Incident 수를 게이지에 반영합니다."""
    incidents_open.set(open_count)


def update_server_risk_metric(server_id: int, server_name: str, risk_score: float) -> None:
    """서버별 실시간 AI 장애 위험 점수 게이지를 업데이트합니다."""
    server_risk_score.labels(server_id=str(server_id), server_name=server_name).set(risk_score)

