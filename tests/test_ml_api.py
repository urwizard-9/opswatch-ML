import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    # lifespan 실행을 트리거하기 위해 TestClient를 context manager로 사용합니다.
    with TestClient(app) as c:
        yield c


def test_get_model_info_success(client):
    """GET /ml/model-info API가 정상 작동하는지 테스트합니다."""
    response = client.get("/ml/model-info")
    assert response.status_code == 200

    data = response.json()
    assert "model_name" in data
    assert "model_alias" in data
    assert "model_version" in data
    assert "is_loaded" in data
    assert data["is_loaded"] is True


def test_predict_risk_success(client):
    """POST /ml/predict-risk API가 정상 예측 결과를 반환하는지 테스트합니다."""
    payload = {
        "response_time_ms": 3500.0,
        "status_code": 200,
        "is_timeout": 0,
        "is_slow": 1,
        "recent_failure_count": 2,
        "importance": 3,
    }
    response = client.post("/ml/predict-risk", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "is_down_pred" in data
    assert "risk_score" in data
    assert "model_name" in data
    assert "model_alias" in data
    assert data["is_down_pred"] in [0, 1]
    assert 0.0 <= data["risk_score"] <= 1.0


def test_predict_risk_invalid_data(client):
    """POST /ml/predict-risk API에 잘못된 데이터 입력 시 422 에러가 발생하는지 검증합니다."""
    # 중요도가 범위를 벗어남 (importance: 5)
    payload = {
        "response_time_ms": 3500.0,
        "status_code": 200,
        "is_timeout": 0,
        "is_slow": 1,
        "recent_failure_count": 2,
        "importance": 5,
    }
    response = client.post("/ml/predict-risk", json=payload)
    assert response.status_code == 422


def test_reload_model_success(client):
    """POST /ml/reload-model API가 정상적으로 모델을 다시 로드하고 200 응답을 주는지 테스트합니다."""
    response = client.post("/ml/reload-model")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "model_info" in data
    assert data["model_info"]["is_loaded"] is True

