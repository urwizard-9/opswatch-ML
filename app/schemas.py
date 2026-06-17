"""OpsWatch Pydantic 스키마 정의."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

# --- Enums ---


class ImportanceLevel(str, Enum):
    """서버 중요도 레벨."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ServerStatus(str, Enum):
    """서버 상태."""

    UP = "UP"
    SLOW = "SLOW"
    DOWN = "DOWN"


class IncidentStatus(str, Enum):
    """장애 상태."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


# --- Server 스키마 ---


class ServerCreate(BaseModel):
    """서버 등록 요청."""

    name: str = Field(..., min_length=1, description="서버 이름")
    url: str = Field(..., min_length=1, description="점검 URL")
    description: str = Field(default="", description="서버 설명")
    importance: ImportanceLevel = Field(default=ImportanceLevel.MEDIUM, description="중요도")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """URL은 http:// 또는 https://로 시작해야 합니다."""
        if not v.startswith(("http://", "https://")):
            msg = "URL은 http:// 또는 https://로 시작해야 합니다"
            raise ValueError(msg)
        return v


class ServerUpdate(BaseModel):
    """서버 수정 요청."""

    name: str | None = None
    url: str | None = None
    description: str | None = None
    importance: ImportanceLevel | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        """URL이 제공된 경우 http:// 또는 https://로 시작해야 합니다."""
        if v is not None and not v.startswith(("http://", "https://")):
            msg = "URL은 http:// 또는 https://로 시작해야 합니다"
            raise ValueError(msg)
        return v


class ServerResponse(BaseModel):
    """서버 응답."""

    id: int
    name: str
    url: str
    description: str | None = None
    importance: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- CheckResult 스키마 ---


class CheckResultResponse(BaseModel):
    """점검 결과 응답."""

    id: int
    server_id: int
    server_name: str | None = None
    status: str
    status_code: int | None = None
    response_time_ms: float | None = None
    message: str | None = None
    checked_at: datetime

    model_config = {"from_attributes": True}


class CheckRunResponse(BaseModel):
    """개별 서버 점검 결과."""

    server_id: int
    server_name: str
    status: str
    status_code: int | None = None
    response_time_ms: float | None = None
    message: str
    checked_at: datetime


class CheckRunAllResponse(BaseModel):
    """전체 서버 점검 결과 요약."""

    total: int
    up: int
    slow: int
    down: int
    results: list[CheckRunResponse]


# --- Incident 스키마 ---


class IncidentResponse(BaseModel):
    """장애 이력 응답."""

    id: int
    server_id: int
    server_name: str | None = None
    status: str
    reason: str | None = None
    action_taken: str | None = None
    github_issue_url: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class IncidentResolveRequest(BaseModel):
    """장애 해결 요청."""

    reason: str = Field(..., description="장애 원인")
    action_taken: str = Field(..., description="조치 내용")


# --- Health 스키마 ---


class HealthResponse(BaseModel):
    """앱 상태 확인 응답."""

    status: str = "ok"
    service: str = "opswatch"
    version: str = "1.0.0"


# --- ML Predict 스키마 ---


class MLPredictRequest(BaseModel):
    """ML 장애 예측 요청 스키마."""

    response_time_ms: float = Field(..., description="응답 시간 (ms)")
    status_code: int = Field(..., description="HTTP 응답 코드")
    is_timeout: int = Field(..., ge=0, le=1, description="타임아웃 여부 (0 또는 1)")
    is_slow: int = Field(..., ge=0, le=1, description="지연 여부 (0 또는 1)")
    recent_failure_count: int = Field(..., ge=0, description="최근 5회 중 실패 횟수")
    importance: int = Field(..., ge=1, le=3, description="서버 중요도 (1: LOW, 2: MEDIUM, 3: HIGH)")


class MLPredictResponse(BaseModel):
    """ML 장애 예측 결과 응답 스키마."""

    is_down_pred: int = Field(..., description="예측 장애 여부 (0: 정상, 1: 장애)")
    risk_score: float = Field(..., description="장애 위험도 점수 (0.0 ~ 1.0)")
    model_name: str = Field(..., description="사용된 모델 이름")
    model_alias: str = Field(..., description="사용된 모델 별칭/태그")

