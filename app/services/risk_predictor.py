import logging

import pandas as pd

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
