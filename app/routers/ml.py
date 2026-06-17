import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas import MLPredictRequest, MLPredictResponse
from app.services.model_loader import get_champion_model_info, load_champion_model
from app.services.risk_predictor import predict_incident_risk

logger = logging.getLogger("opswatch")

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post("/reload-model", status_code=status.HTTP_200_OK)
def reload_model():
    """MLflow Model Registry에서 champion 모델을 동적으로 다시 로드하여 캐시를 갱신합니다."""
    try:
        load_champion_model()
        info = get_champion_model_info()
        logger.info(f"ML_ROUTE_RELOAD_SUCCESS | version={info['model_version']}")
        return {
            "status": "success",
            "message": "Model cache reloaded successfully.",
            "model_info": info,
        }
    except Exception as e:
        logger.error(f"ML_ROUTE_RELOAD_ERROR | Failed to reload model | err={e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to reload model: {e}",
        )



@router.get("/model-info", status_code=status.HTTP_200_OK)
def get_model_info():
    """현재 메모리에 로드된 서빙 Champion 모델의 메타데이터 정보를 반환합니다."""
    info = get_champion_model_info()
    if not info["is_loaded"]:
        logger.error("ML_ROUTE_ERROR | Active model is not loaded.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Machine learning model is not loaded yet.",
        )
    return info


@router.post(
    "/predict-risk", response_model=MLPredictResponse, status_code=status.HTTP_200_OK
)
def predict_risk(request: MLPredictRequest):
    """주어진 모니터링 피처를 바탕으로 실시간 장애 위험 여부 및 확률을 예측합니다."""
    try:
        prediction = predict_incident_risk(request)
        info = get_champion_model_info()
        return MLPredictResponse(
            is_down_pred=prediction["is_down_pred"],
            risk_score=prediction["risk_score"],
            model_name=info["model_name"],
            model_alias=info["model_alias"],
        )
    except RuntimeError as e:
        logger.error(f"ML_ROUTE_ERROR | Prediction failed | err={e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        )
    except Exception as e:
        logger.exception(f"ML_ROUTE_UNEXPECTED_ERROR | err={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during prediction: {e}",
        )
