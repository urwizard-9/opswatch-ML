"""health, metrics 엔드포인트 및 메트릭 업데이트 테스트."""

from unittest.mock import patch


def test_health(client):
    """/health 응답 확인."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "opswatch"
    assert "version" in data


def test_metrics_endpoint_accessible(client):
    """/metrics 엔드포인트 접근 및 Prometheus 포맷 확인."""
    res = client.get("/metrics")
    assert res.status_code == 200
    # Prometheus 텍스트 포맷 특징: # HELP 라인 존재
    assert b"# HELP" in res.content


def test_metrics_contains_opswatch_metrics(client):
    """/metrics에 OpsWatch 전용 메트릭이 포함되어야 함."""
    res = client.get("/metrics")
    content = res.text
    assert "opswatch_checks_total" in content
    assert "opswatch_servers_up" in content
    assert "opswatch_servers_down" in content
    assert "opswatch_incidents_open" in content
    assert "opswatch_response_time_ms" in content


def test_metrics_counter_increments_after_check(client):
    """점검 후 opswatch_checks_total 카운터가 메트릭에 나타나야 함."""
    res = client.post("/servers", json={"name": "m-srv", "url": "http://m.com"})
    sid = res.json()["id"]

    # monitor_service 전체를 패치하지 않고 실제 check_server가 메트릭 업데이트까지 실행하도록
    # httpx 요청만 mock해서 DOWN 응답 시뮬레이션
    from unittest.mock import MagicMock

    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("app.services.monitor_service.httpx.get", return_value=mock_response):
        client.post(f"/checks/run/{sid}")

    after = client.get("/metrics").text
    assert 'opswatch_checks_total{status="DOWN"}' in after


def test_mock_normal(client):
    """GET /mock/normal → 200."""
    res = client.get("/mock/normal")
    assert res.status_code == 200


def test_mock_error(client):
    """GET /mock/error → 500."""
    res = client.get("/mock/error")
    assert res.status_code == 500


def test_mock_crash(client):
    """GET /mock/crash → 500 (RuntimeError 발생)."""
    # /mock/crash는 의도적 예외를 발생하므로 raise_server_exceptions=False로 호출
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from tests.conftest import override_get_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as crash_client:
        res = crash_client.get("/mock/crash")
    assert res.status_code == 500
