"""Incident API 테스트."""

from unittest.mock import patch


def _setup_down_incident(client) -> tuple[int, int]:
    """헬퍼: 서버 등록 → DOWN 점검 → Incident 생성 후 (server_id, incident_id) 반환."""
    res = client.post("/servers", json={"name": "err-srv", "url": "http://err.com"})
    sid = res.json()["id"]

    with patch("app.services.monitor_service.check_server") as mock_check:
        mock_check.return_value = {
            "status": "DOWN",
            "status_code": 500,
            "response_time_ms": 100.0,
            "message": "HTTP 500 오류",
        }
        client.post(f"/checks/run/{sid}")

    incidents = client.get("/incidents").json()
    return sid, incidents[0]["id"]


def test_list_incidents_empty(client):
    """초기 상태에서 Incident 목록은 비어있음."""
    res = client.get("/incidents")
    assert res.status_code == 200
    assert res.json() == []


def test_list_incidents_after_down(client):
    """DOWN 점검 후 OPEN Incident 1개 생성."""
    _setup_down_incident(client)
    res = client.get("/incidents")
    assert len(res.json()) == 1
    assert res.json()[0]["status"] == "OPEN"


def test_filter_incidents_by_status(client):
    """status 파라미터로 필터링."""
    _, iid = _setup_down_incident(client)

    # OPEN 필터
    res = client.get("/incidents?status=OPEN")
    assert len(res.json()) == 1

    # RESOLVED 필터 (아직 없음)
    res = client.get("/incidents?status=RESOLVED")
    assert len(res.json()) == 0


def test_get_incident_detail(client):
    """특정 Incident 상세 조회."""
    _, iid = _setup_down_incident(client)
    res = client.get(f"/incidents/{iid}")
    assert res.status_code == 200
    assert res.json()["id"] == iid


def test_get_incident_not_found(client):
    """존재하지 않는 Incident 조회 시 404."""
    res = client.get("/incidents/999")
    assert res.status_code == 404


def test_resolve_incident(client):
    """Incident 해결 처리 후 RESOLVED, resolved_at 기록."""
    _, iid = _setup_down_incident(client)

    res = client.put(
        f"/incidents/{iid}/resolve",
        json={
            "reason": "메모리 누수로 인한 다운",
            "action_taken": "서버 재시작 및 메모리 캐시 초기화",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "RESOLVED"
    assert data["reason"] == "메모리 누수로 인한 다운"
    assert data["action_taken"] == "서버 재시작 및 메모리 캐시 초기화"
    assert data["resolved_at"] is not None


def test_resolve_incident_already_resolved(client):
    """이미 RESOLVED된 Incident 재해결 시 400."""
    _, iid = _setup_down_incident(client)
    body = {"reason": "r", "action_taken": "a"}

    client.put(f"/incidents/{iid}/resolve", json=body)  # 1차 해결
    res = client.put(f"/incidents/{iid}/resolve", json=body)  # 2차 시도
    assert res.status_code == 400


def test_new_incident_after_resolve(client):
    """해결 후 같은 서버 재DOWN 시 새 Incident 생성."""
    sid, iid = _setup_down_incident(client)
    client.put(f"/incidents/{iid}/resolve", json={"reason": "r", "action_taken": "a"})

    # 동일 서버 재DOWN
    with patch("app.services.monitor_service.check_server") as mock_check:
        mock_check.return_value = {
            "status": "DOWN",
            "status_code": 500,
            "response_time_ms": 100.0,
            "message": "HTTP 500 오류",
        }
        client.post(f"/checks/run/{sid}")

    all_incidents = client.get("/incidents").json()
    assert len(all_incidents) == 2  # 첫 RESOLVED + 새 OPEN
    open_ones = [i for i in all_incidents if i["status"] == "OPEN"]
    assert len(open_ones) == 1
