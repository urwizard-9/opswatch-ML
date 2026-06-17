import logging
import os

import joblib
import mlflow
import mlflow.sklearn

from app.config import settings

logger = logging.getLogger("opswatch")

# 전역 모델 캐시 변수
_loaded_model = None
_loaded_model_version = None


def get_champion_model():
    """현재 캐싱된 모델 객체를 반환합니다."""
    global _loaded_model
    return _loaded_model


def get_champion_model_info():
    """현재 캐싱된 모델의 메타데이터 정보를 반환합니다."""
    global _loaded_model, _loaded_model_version
    return {
        "model_name": settings.MLFLOW_MODEL_NAME,
        "model_alias": settings.MLFLOW_MODEL_ALIAS,
        "model_version": _loaded_model_version,
        "is_loaded": _loaded_model is not None,
    }


def load_champion_model():
    """MLflow Model Registry에서 'champion' 별칭을 가진 모델을 동적으로 로드합니다.

    실패 시 로컬 백업 joblib 파일로 Fallback합니다.
    """
    global _loaded_model, _loaded_model_version

    # 1. 인증 및 트래킹 설정 (환경변수 우선적 조회)
    if "MLFLOW_TRACKING_USERNAME" not in os.environ:
        os.environ["MLFLOW_TRACKING_USERNAME"] = settings.MLFLOW_TRACKING_USERNAME
    if "MLFLOW_TRACKING_PASSWORD" not in os.environ:
        os.environ["MLFLOW_TRACKING_PASSWORD"] = settings.MLFLOW_TRACKING_PASSWORD

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", settings.MLFLOW_TRACKING_URI)
    mlflow.set_tracking_uri(tracking_uri)

    model_uri = f"models:/{settings.MLFLOW_MODEL_NAME}@{settings.MLFLOW_MODEL_ALIAS}"
    logger.info(f"MLFLOW_MODEL_LOAD_START | uri={model_uri}")

    try:
        # MLflow API를 통한 동적 모델 로딩
        model = mlflow.sklearn.load_model(model_uri)

        # 모델의 버전을 파악하기 위해 MLflow Client API 호출
        try:
            client = mlflow.tracking.MlflowClient(tracking_uri)
            mv = client.get_model_version_by_alias(
                settings.MLFLOW_MODEL_NAME, settings.MLFLOW_MODEL_ALIAS
            )
            _loaded_model_version = mv.version
        except Exception as client_err:
            logger.warning(f"MLFLOW_MODEL_VERSION_FETCH_FAILED | err={client_err}")
            _loaded_model_version = "unknown_alias"

        _loaded_model = model
        logger.info(f"MLFLOW_MODEL_LOAD_SUCCESS | version={_loaded_model_version}")
        return model

    except Exception as e:
        logger.warning(
            f"MLFLOW_MODEL_LOAD_FAILED | err={e} | Attempting fallback to local model"
        )

        # 2. 로컬 Fallback 모델 로딩
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_path = os.path.join(base_dir, "ml", "artifacts", "incident_model.joblib")

        if os.path.exists(local_path):
            try:
                model = joblib.load(local_path)
                _loaded_model = model
                _loaded_model_version = "local_fallback"
                logger.info(f"LOCAL_MODEL_LOAD_SUCCESS | path={local_path}")
                return model
            except Exception as local_err:
                logger.error(
                    f"LOCAL_MODEL_LOAD_FAILED | path={local_path} | err={local_err}"
                )
                raise RuntimeError(
                    "Failed to load both remote MLflow and local fallback models."
                ) from local_err
        else:
            logger.error(f"LOCAL_MODEL_NOT_FOUND | path={local_path}")
            raise RuntimeError(
                "MLflow model load failed and local fallback model not found."
            ) from e
