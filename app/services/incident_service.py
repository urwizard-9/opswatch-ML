"""OpsWatch 장애 이력 서비스.

DOWN 판정 시 Incident를 자동 생성하고, 중복 생성을 방지합니다.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import Incident

logger = get_logger(__name__)


def create_incident_if_needed(db: Session, server_id: int, reason: str) -> Incident | None:
    """DOWN 발생 시 해당 서버에 OPEN 상태의 Incident가 없으면 새로 생성합니다.

    이미 OPEN 상태의 Incident가 있으면 중복 생성하지 않고 None을 반환합니다.

    Args:
        db: DB 세션
        server_id: 장애가 발생한 서버 ID
        reason: 장애 원인 메시지

    Returns:
        생성된 Incident 또는 None (이미 OPEN Incident 존재 시)
    """
    existing = (
        db.query(Incident)
        .filter(
            Incident.server_id == server_id,
            Incident.status == "OPEN",
        )
        .first()
    )

    if existing:
        logger.info(
            "INCIDENT_DUPLICATE_SKIPPED | server_id=%d | 기존 OPEN Incident #%d",
            server_id,
            existing.id,
        )
        return None

    incident = Incident(
        server_id=server_id,
        status="OPEN",
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    logger.warning(
        "INCIDENT_CREATED | id=%d | server_id=%d | reason=%s", incident.id, server_id, reason
    )
    return incident


def resolve_incident(db: Session, incident: Incident, reason: str, action_taken: str) -> Incident:
    """OPEN 상태의 Incident를 RESOLVED로 변경합니다.

    Args:
        db: DB 세션
        incident: 해결할 Incident 객체
        reason: 장애 원인
        action_taken: 조치 내용

    Returns:
        해결 처리된 Incident
    """
    incident.status = "RESOLVED"
    incident.reason = reason
    incident.action_taken = action_taken
    incident.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(incident)
    logger.info(
        "INCIDENT_RESOLVED | id=%d | server_id=%d | action=%s",
        incident.id,
        incident.server_id,
        action_taken,
    )
    return incident
