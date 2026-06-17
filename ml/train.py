import argparse
import os
import sys

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score

from app.config import settings

# Windows 터미널(CP949)에서 MLflow 이모지 출력 시 발생하는 UnicodeEncodeError 방지
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


def train_model():

    # MLflow 타임아웃 및 재시도 횟수 제한 설정 (프로세스 행 방지)
    os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] = "10"
    os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] = "1"

    # CLI 인자 분석
    parser = argparse.ArgumentParser(description="OpsWatch ML Model Training CLI")
    parser.add_argument("--model-type", type=str, default="rf", choices=["rf", "lr"],
                        help="Model type to train: rf (RandomForest) or lr (LogisticRegression)")
    parser.add_argument("--n-estimators", type=int, default=100, help="Number of trees in RandomForest")
    parser.add_argument("--max-depth", type=int, default=5, help="Max depth of trees in RandomForest")
    parser.add_argument("--c-reg", type=float, default=1.0, help="Inverse of regularization strength in LogisticRegression")
    parser.add_argument("--data-path", type=str, default=None, help="Path to training data CSV")
    parser.add_argument("--run-name", type=str, default="model-training", help="MLflow Run Name")
    args = parser.parse_args()

    # 1. 실행 가이드 및 경로 세팅
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    if args.data_path:
        if os.path.isabs(args.data_path):
            train_path = args.data_path
        else:
            # 최상위 워크스페이스 기준 또는 상대경로
            train_path = os.path.abspath(args.data_path)
             # v2 실행 시 "ml/data/train_v2.csv"가 동적 할당됨
    else:
        train_path = os.path.join(base_dir, "data", "train.csv")
        
    test_path = os.path.join(base_dir, "data", "test.csv")

    if not os.path.exists(train_path) or not os.path.exists(test_path):
        print(f"Error: 학습용 CSV 데이터셋 파일이 존재하지 않습니다. (path: {train_path})")
        return

    # 2. 데이터셋 로드
    df_train = pd.read_csv(train_path)
    df_test = pd.read_csv(test_path)

    feature_cols = [
        "response_time_ms",
        "status_code",
        "is_timeout",
        "is_slow",
        "recent_failure_count",
        "importance",
    ]
    target_col = "is_down"

    X_train = df_train[feature_cols]
    y_train = df_train[target_col]
    X_test = df_test[feature_cols]
    y_test = df_test[target_col]

    # 3. 모델 정의 및 로컬 학습 진행
    if args.model_type == "rf":
        print(f"Training RandomForestClassifier (n_estimators={args.n_estimators}, max_depth={args.max_depth}) from {train_path}")
        model = RandomForestClassifier(
            n_estimators=args.n_estimators, max_depth=args.max_depth, random_state=42
        )
    elif args.model_type == "lr":
        print(f"Training LogisticRegression (C={args.c_reg}) from {train_path}")
        model = LogisticRegression(
            C=args.c_reg, max_iter=1000, random_state=42
        )
    else:
        raise ValueError(f"Unknown model type: {args.model_type}")

    model.fit(X_train, y_train)

    # 4. 성능지표 계산
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)

    train_acc = accuracy_score(y_train, y_train_pred)
    test_acc = accuracy_score(y_test, y_test_pred)
    test_f1 = f1_score(y_test, y_test_pred)

    print("=== Model Training Completed Locally ===")
    print(f"Train Accuracy: {train_acc:.4f}")
    print(f"Test Accuracy : {test_acc:.4f}")
    print(f"Test F1-Score : {test_f1:.4f}")

    # 임시 아티팩트 디렉터리 보장
    artifacts_dir = os.path.join(base_dir, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    local_model_path = os.path.join(artifacts_dir, "incident_model.joblib")

    # 5. MLflow 트래킹 및 예외 전파/Fallback 분기 처리
    allow_fallback = os.getenv("ALLOW_MLFLOW_FALLBACK", "false").lower() == "true"

    # MLflow 인증 정보 획득 (Basic Auth 대응)
    os.environ["MLFLOW_TRACKING_USERNAME"] = settings.MLFLOW_TRACKING_USERNAME
    os.environ["MLFLOW_TRACKING_PASSWORD"] = settings.MLFLOW_TRACKING_PASSWORD

    try:
        # MLflow Tracking & Registry 설정
        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_registry_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment("opswatch-incident-classification")

        with mlflow.start_run(run_name=args.run_name) as run:
            # 파라미터 기록
            if args.model_type == "rf":
                mlflow.log_param("model_type", "RandomForestClassifier")
                mlflow.log_param("n_estimators", args.n_estimators)
                mlflow.log_param("max_depth", args.max_depth)
            elif args.model_type == "lr":
                mlflow.log_param("model_type", "LogisticRegression")
                mlflow.log_param("C", args.c_reg)
                
            mlflow.log_param("random_state", 42)
            mlflow.log_param("feature_columns", ",".join(feature_cols))
            mlflow.log_param("train_row_count", len(df_train))
            mlflow.log_param("test_row_count", len(df_test))

            # 메트릭 기록
            mlflow.log_metric("train_accuracy", train_acc)
            mlflow.log_metric("test_accuracy", test_acc)
            mlflow.log_metric("test_f1", test_f1)

            # 데이터셋 파일 로컬 로깅 백업
            joblib.dump(model, local_model_path)
            print(f"Saved local backup model to {local_model_path}")

            # 아티팩트 업로드
            mlflow.log_artifact(train_path)
            mlflow.log_artifact(test_path)
            mlflow.log_artifact(local_model_path)

            # Model Registry 등록
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path="model",
                registered_model_name="opswatch-incident-model",
            )

            print("Successfully uploaded model and logs to MLflow Server.")
            print(f"MLflow Run ID: {run.info.run_id}")

    except Exception as e:
        if allow_fallback:
            print(
                f"Warning: MLflow 업로드에 실패했으나 fallback이 활성화되어 진행합니다. 에러: {e}"
            )
            joblib.dump(model, local_model_path)
            print(f"Saved fallback model locally to {local_model_path}")
        else:
            print("Error: MLflow 업로드 실패! (ALLOW_MLFLOW_FALLBACK=false)")
            raise e


if __name__ == "__main__":
    train_model()
