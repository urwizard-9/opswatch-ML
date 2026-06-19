import logging

import pandas as pd
from sqlalchemy.orm import Session

from app.models import CheckResult, Server
from app.schemas import MLPredictRequest
from app.services.model_loader import get_champion_model

logger = logging.getLogger("opswatch")


def predict_incident_risk(request: MLPredictRequest) -> dict:
    """입력 피처를 기반으로 장애 예측 및 위험도를 도출합니다."""
    model = get_champion_model()
    if model is None:
        logger.error("ML_PREDICT_ERROR | Model is not loaded in memory.")
        raise RuntimeError(
            "ML model is not loaded. Please ensure the server is fully initialized."
        )

    # 1. 피처 컬럼을 정확한 순서로 DataFrame 구성
    feature_data = {
        "response_time_ms": [request.response_time_ms],
        "status_code": [request.status_code],
        "is_timeout": [request.is_timeout],
        "is_slow": [request.is_slow],
        "recent_failure_count": [request.recent_failure_count],
        "importance": [request.importance],
    }
    df = pd.DataFrame(feature_data)

    # 2. 모델 예측 수행
    try:
        is_down_pred = int(model.predict(df)[0])

        # 장애 확률 (1일 확률)
        probabilities = model.predict_proba(df)[0]
        risk_score = (
            float(probabilities[1]) if len(probabilities) > 1 else float(is_down_pred)
        )

        logger.info(f"ML_PREDICT_SUCCESS | pred={is_down_pred} | risk={risk_score:.4f}")
        return {"is_down_pred": is_down_pred, "risk_score": risk_score}
    except Exception as e:
        logger.exception(f"ML_PREDICT_FAILED | err={e}")
        raise RuntimeError(f"Error occurred during model prediction: {e}") from e


def predict_realtime_server_risk(db: Session, server: Server, result: dict) -> dict:
    """실시간 점검 결과를 바탕으로 머신러닝 장애 예측을 수행합니다."""
    # 1. 최근 5회 중 실패(DOWN) 횟수 계산
    recent_results = (
        db.query(CheckResult)
        .filter(CheckResult.server_id == server.id)
        .order_by(CheckResult.checked_at.desc())
        .limit(5)
        .all()
    )
    recent_failures = sum(1 for r in recent_results if r.status == "DOWN")

    # 2. 중요도 문자열을 숫자로 매핑 (LOW=1, MEDIUM=2, HIGH=3)
    importance_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    importance_str = server.importance.value if hasattr(server.importance, "value") else str(server.importance)
    importance_num = importance_map.get(importance_str.upper(), 2)

    # 3. is_slow 및 is_timeout 판별
    is_slow = 1 if result.get("status") == "SLOW" else 0
    message_lower = (result.get("message") or "").lower()
    is_timeout = 1 if "timeout" in message_lower or "시간 초과" in message_lower or "연결 실패" in message_lower else 0

    # 4. MLPredictRequest 생성
    # Timeout 또는 연결 실패일 경우 학습 데이터의 표현 방식(5000ms)과 정합성을 맞춤
    default_response_time = 5000.0 if is_timeout == 1 else 0.0
    req = MLPredictRequest(
        response_time_ms=float(result.get("response_time_ms") or default_response_time),
        status_code=int(result.get("status_code") or 0),
        is_timeout=is_timeout,
        is_slow=is_slow,
        recent_failure_count=recent_failures,
        importance=importance_num,
    )

    return predict_incident_risk(req)
