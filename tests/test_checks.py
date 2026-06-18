"""상태 점검 API 테스트.

실제 HTTP 요청 대신 mock_targets 엔드포인트를 활용합니다.
"""

from unittest.mock import patch


def _register_server(client, name: str, url: str, importance: str = "MEDIUM") -> int:
    """헬퍼: 서버 등록 후 ID 반환."""
    res = client.post("/servers", json={"name": name, "url": url, "importance": importance})
    return res.json()["id"]


def test_check_single_up(client):
    """UP 상태 서버 점검 결과 확인."""
    sid = _register_server(client, "normal", "http://localhost:8000/mock/normal")

    # monitor_service.check_server를 mock으로 대체
    with patch("app.services.monitor_service.check_server") as mock_check:
        mock_check.return_value = {
            "status": "UP",
            "status_code": 200,
            "response_time_ms": 50.0,
            "message": "정상 응답 (50ms)",
        }
        res = client.post(f"/checks/run/{sid}")

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UP"
    assert data["status_code"] == 200
    assert data["server_id"] == sid


def test_check_single_slow(client):
    """SLOW 상태 서버 점검 결과 확인."""
    sid = _register_server(client, "slow", "http://localhost:8000/mock/slow")

    with patch("app.services.monitor_service.check_server") as mock_check:
        mock_check.return_value = {
            "status": "SLOW",
            "status_code": 200,
            "response_time_ms": 3000.0,
            "message": "응답 성공, 지연 발생 (3000ms)",
        }
        res = client.post(f"/checks/run/{sid}")

    assert res.status_code == 200
    assert res.json()["status"] == "SLOW"


def test_check_single_down_creates_incident(client):
    """DOWN 시 Incident 자동 생성 확인."""
    sid = _register_server(client, "error", "http://localhost:8000/mock/error")

    with patch("app.services.monitor_service.check_server") as mock_check:
        mock_check.return_value = {
            "status": "DOWN",
            "status_code": 500,
            "response_time_ms": 100.0,
            "message": "HTTP 500 오류",
        }
        res = client.post(f"/checks/run/{sid}")

    assert res.status_code == 200
    assert res.json()["status"] == "DOWN"

    # Incident 자동 생성 확인
    incidents = client.get("/incidents").json()
    assert len(incidents) == 1
    assert incidents[0]["status"] == "OPEN"
    assert incidents[0]["server_id"] == sid


def test_check_single_down_no_duplicate_incident(client):
    """DOWN이 반복돼도 Incident는 1개만 생성."""
    sid = _register_server(client, "error2", "http://localhost:8000/mock/error")
    down_result = {
        "status": "DOWN",
        "status_code": 500,
        "response_time_ms": 100.0,
        "message": "HTTP 500 오류",
    }

    with patch("app.services.monitor_service.check_server") as mock_check:
        mock_check.return_value = down_result
        client.post(f"/checks/run/{sid}")
        client.post(f"/checks/run/{sid}")  # 두 번째 DOWN
        client.post(f"/checks/run/{sid}")  # 세 번째 DOWN

    incidents = client.get("/incidents").json()
    assert len(incidents) == 1  # 중복 방지 - 여전히 1개


def test_check_single_server_not_found(client):
    """존재하지 않는 서버 점검 시 404."""
    res = client.post("/checks/run/999")
    assert res.status_code == 404


def test_check_single_inactive_server(client):
    """비활성 서버 점검 시 400."""
    sid = _register_server(client, "inactive", "http://example.com")
    client.put(f"/servers/{sid}", json={"is_active": False})
    res = client.post(f"/checks/run/{sid}")
    assert res.status_code == 400


def test_check_all(client):
    """전체 서버 점검 집계 결과 확인."""
    _register_server(client, "s1", "http://a.com")
    _register_server(client, "s2", "http://b.com")

    results_map = {
        "http://a.com": {
            "status": "UP",
            "status_code": 200,
            "response_time_ms": 100.0,
            "message": "ok",
        },
        "http://b.com": {
            "status": "DOWN",
            "status_code": 500,
            "response_time_ms": 200.0,
            "message": "error",
        },
    }

    def side_effect(url):
        return results_map[url]

    with patch("app.services.monitor_service.check_server", side_effect=side_effect):
        res = client.post("/checks/run")

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert data["up"] == 1
    assert data["down"] == 1


def test_check_history(client):
    """점검 이력 조회."""
    sid = _register_server(client, "hist", "http://example.com")

    with patch("app.services.monitor_service.check_server") as mock_check:
        mock_check.return_value = {
            "status": "UP",
            "status_code": 200,
            "response_time_ms": 50.0,
            "message": "ok",
        }
        client.post(f"/checks/run/{sid}")
        client.post(f"/checks/run/{sid}")

    res = client.get(f"/checks/history/{sid}")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_realtime_prediction_during_check(client):
    """상태 점검 시 실시간 AI 장애 위험 예측 및 Prometheus 메트릭 갱신이 일어나는지 검증."""
    sid = _register_server(client, "ai-test-server", "http://localhost:8000/mock/normal", importance="HIGH")

    # 1. 점검 실행
    with patch("app.services.monitor_service.check_server") as mock_check:
        mock_check.return_value = {
            "status": "UP",
            "status_code": 200,
            "response_time_ms": 100.0,
            "message": "정상 작동 중",
        }
        res = client.post(f"/checks/run/{sid}")

    assert res.status_code == 200

    # 2. Prometheus 메트릭(/metrics)에 실시간 위험 점수 수집 게이지가 포함되어 있는지 검증
    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    assert "opswatch_server_risk_score" in metrics_res.text

