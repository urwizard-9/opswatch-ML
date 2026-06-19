# 🔍 OpsWatch

**배포 서버 통신 상태 모니터링 및 장애 이력관리 DevOps 시스템**

> 여러 서버/API의 통신 상태를 점검하여 UP/SLOW/DOWN을 판별하고,
> 점검 이력·장애 이력·로그·메트릭을 관리하는 FastAPI 기반 운영 모니터링 시스템

---

## 📋 프로젝트 개요

| 항목 | 내용 |
|---|---|
| **프로젝트** | 인공지능파이프라인 기말 프로젝트 (26-1) |
| **기술 스택** | Python 3.13 / FastAPI / SQLAlchemy / Prometheus / Grafana / MLflow |
| **배포** | Docker / Render (FastAPI) |
| **배포 URL** | https://opswatch-ml-service.onrender.com |
| **CI/CD** | GitHub Actions (ruff + pytest + Docker 빌드 + ML 학습 자동화) |
| **테스트** | pytest 35개, 커버리지 80%+ |

---

## 🏗️ DevOps & MLOps 파이프라인

```
[코드/데이터 수정] ➔ Git Push ➔ GitHub Actions CI/CD
    ├─ ci.yml: ruff 코드 품질 검사 + pytest (35개 테스트 검증)
    ├─ docker-verify.yml: Docker 빌드 + Smoke Test (/health, /ml/model-info 확인)
    └─ train.yml: MLflow 연동 RandomForest/Logistic Regression 학습 및 트래킹 자동화
    ↓
[Render 자동 배포] (main 브랜치)
    ↓
[MLflow Model Registry] ➔ Champion 모델 에일리어스(Alias) 지정 (운영자)
    ↓
[FastAPI 서비스 운영]
    ├─ MLflow Registry 기반 Champion 모델 적재 (이중화 Fallback 지원)
    ├─ 60초 백그라운드 스케줄러 ➔ run_monitoring_pipeline() 실행
    │   ├─ 상태 점검 (UP/SLOW/DOWN) 및 DB 저장 (CheckResult)
    │   ├─ Champion 모델 기반 실시간 장애 위험 예측 및 로그/경고 로깅
    │   ├─ Prometheus 게이지 메트릭 갱신 (opswatch_server_risk_score)
    │   └─ DOWN 감지 ➔ Incident 자동 생성 (중복 방지)
    └─ /ml/reload-model API ➔ 서비스 중단 없는 실시간 롤백 및 캐시 갱신
    ↓
[Prometheus & Grafana] (로컬 모니터링)
    ├─ Prometheus: Render 메트릭 스크레이프
    └─ Grafana 대시보드: 실시간 AI 장애 위험 점수 추이 및 서버 통계 시각화
```

---

## 🚀 빠른 시작

### 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000

# API 문서 확인
# http://localhost:8000/docs
```

### Docker Compose (모니터링 스택 포함)

```bash
docker-compose up -d --build
```

| 서비스 | URL |
|---|---|
| OpsWatch API | http://localhost:8000 |
| Swagger 문서 | http://localhost:8000/docs |
| Prometheus | http://localhost:19090 |
| Grafana | http://localhost:13000 (admin / opswatch123) |

### 테스트

```bash
# 전체 테스트 + 커버리지
pytest tests/ --cov=app --cov-report=term-missing

# ruff 린트 검사
ruff check app/ tests/
```

---

## 📡 API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | 앱 상태 확인 |
| `POST` | `/servers` | 서버 등록 |
| `GET` | `/servers` | 서버 목록 조회 |
| `GET` | `/servers/{id}` | 서버 상세 조회 |
| `PUT` | `/servers/{id}` | 서버 정보 수정 |
| `DELETE` | `/servers/{id}` | 서버 삭제 |
| `POST` | `/checks/run/{id}` | 개별 서버 점검 |
| `POST` | `/checks/run` | 전체 서버 점검 |
| `GET` | `/checks/history/{id}` | 점검 이력 조회 |
| `GET` | `/incidents` | 장애 이력 조회 |
| `GET` | `/incidents/{id}` | 장애 상세 조회 |
| `PUT` | `/incidents/{id}/resolve` | 장애 해결 처리 |
| `GET` | `/metrics` | Prometheus 메트릭 |
| `GET` | `/ml/model-info` | ML: 서빙 중인 모델 메타정보 조회 |
| `POST` | `/ml/predict-risk` | ML: 장애 확률 수동 추론 (검증용) |
| `POST` | `/ml/reload-model` | ML: 최신 Champion 모델 런타임 무중단 갱신/롤백 |
| `GET` | `/mock/normal` | Mock: 정상 응답 (200) |
| `GET` | `/mock/slow` | Mock: 지연 응답 (3초) |
| `GET` | `/mock/error` | Mock: 에러 응답 (500) |
| `GET` | `/mock/random` | Mock: 랜덤 응답 |
| `GET` | `/mock/crash` | Mock: 의도적 예외 |

---

## 📊 Prometheus 메트릭

| 메트릭 | 타입 | 설명 |
|---|---|---|
| `opswatch_checks_total` | Counter | 총 점검 횟수 (status 라벨) |
| `opswatch_servers_up` | Gauge | 현재 UP 서버 수 |
| `opswatch_servers_slow` | Gauge | 현재 SLOW 서버 수 |
| `opswatch_servers_down` | Gauge | 현재 DOWN 서버 수 |
| `opswatch_incidents_open` | Gauge | 현재 OPEN Incident 수 |
| `opswatch_response_time_ms` | Histogram | 응답 시간 분포 |
| `opswatch_server_risk_score` | Gauge | AI 기반 실시간 장애 위험 점수 (server_name 라벨) |

---

## 📁 프로젝트 구조

```
opswatch/
├── app/
│   ├── main.py                  # FastAPI 진입점 + lifespan
│   ├── database.py              # SQLAlchemy 데이터베이스 설정
│   ├── models.py                # ORM 모델 정의 (Server, CheckResult, Incident)
│   ├── schemas.py               # Pydantic 스키마 정의 (MLPredictRequest 등 포함)
│   ├── config.py                # 환경변수 및 MLflow 설정
│   ├── model_loader.py          # MLflow Model Registry Champion 로더
│   ├── logging_config.py        # 구조화된 운영 로깅 설정
│   ├── routers/
│   │   ├── servers.py           # Server CRUD
│   │   ├── checks.py            # 상태 점검
│   │   ├── incidents.py         # 장애 이력
│   │   ├── metrics.py           # Prometheus /metrics
│   │   ├── ml.py                # ML API (/ml/model-info, /ml/reload-model 등)
│   │   └── mock_targets.py      # Mock 대상 서버 시뮬레이터
│   └── services/
│       ├── monitor_service.py   # httpx 점검 + AI 예측 연동 파이프라인
│       ├── incident_service.py  # Incident 자동 생성 및 완충 관리
│       ├── risk_predictor.py    # scikit-learn Champion 기반 실시간 장애 예측
│       └── scheduler.py         # 백그라운드 자동 모니터링 스케줄러
├── ml/
│   ├── data/
│   │   ├── train_v2.csv         # ML 학습용 증강 데이터셋
│   │   └── test.csv             # ML 평가용 검증 데이터셋
│   └── train.py                 # RF/LR 다중 모델 학습 및 MLflow 트래킹 연동 스크립트
├── tests/                       # 통합 테스트 suite (총 35개)
├── prometheus/                  # Prometheus 설정
├── grafana/                     # Grafana 프로비저닝 (실시간 AI 위험 지수 시각화 대시보드)
├── .github/workflows/           # CI/CD & MLOps 워크플로우 (ci.yml, docker-verify.yml, train.yml)
├── Dockerfile                   # 멀티스테이지 컨테이너 빌드
├── docker-compose.yml           # Prometheus/Grafana 로컬 시각화 스택
├── render.yaml                  # Render IaC Blueprint 설정
├── pyproject.toml               # ruff/pytest/pythonpath 구성 설정
└── requirements.txt             # 패키지 의존성 정의
```

---

## 📝 커밋 메시지 규칙

```
<type>: <설명>
```

| Type | 의미 | 예시 |
|---|---|---|
| `feat` | 새로운 기능 추가 | `feat: 서버 등록 API 구현` |
| `fix` | 버그 수정 | `fix: slow 응답 판별 기준 수정` |
| `test` | 테스트 추가/수정 | `test: 서버 등록 API 테스트 추가` |
| `ci` | CI/CD 설정 변경 | `ci: GitHub Actions 워크플로우 추가` |
| `chore` | 빌드, 도구, 설정 변경 | `chore: Dockerfile 추가` |
| `docs` | 문서 작성/수정 | `docs: README 작성` |
| `refactor` | 기능 변경 없는 구조 개선 | `refactor: 상태 점검 로직 분리` |
| `style` | 코드 스타일 변경 | `style: ruff 린트 경고 수정` |

---

## 📜 라이선스

MIT License
