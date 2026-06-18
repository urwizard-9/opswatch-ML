"""OpsWatch 상태 점검 API 라우터."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CheckResult, Server
from app.schemas import CheckResultResponse, CheckRunAllResponse, CheckRunResponse
from app.services.monitor_service import run_monitoring_pipeline

logger = logging.getLogger("opswatch")

router = APIRouter(prefix="/checks", tags=["Checks"])


@router.post("/run/{server_id}", response_model=CheckRunResponse)
async def run_check_single(server_id: int, db: Session = Depends(get_db)):
    """특정 서버 1대를 점검합니다."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다")
    if not server.is_active:
        raise HTTPException(status_code=400, detail="비활성 서버는 점검할 수 없습니다")

    # 공통 모니터링 파이프라인 수행 (점검 ➔ 저장 ➔ 준실시간 AI 추론 ➔ 메트릭 ➔ Incident 생성)
    result = await run_monitoring_pipeline(db, server)
    now = datetime.now(timezone.utc)

    return CheckRunResponse(
        server_id=server.id,
        server_name=server.name,
        status=result["status"],
        status_code=result["status_code"],
        response_time_ms=result["response_time_ms"],
        message=result["message"],
        checked_at=now,
    )


@router.post("/run", response_model=CheckRunAllResponse)
async def run_check_all(db: Session = Depends(get_db)):
    """활성화된 전체 서버를 점검합니다."""
    servers = db.query(Server).filter(Server.is_active == True).all()  # noqa: E712
    if not servers:
        raise HTTPException(status_code=404, detail="활성 서버가 없습니다")

    results = []
    now = datetime.now(timezone.utc)

    for server in servers:
        # 공통 모니터링 파이프라인 수행 (점검 ➔ 저장 ➔ 준실시간 AI 추론 ➔ 메트릭 ➔ Incident 생성)
        result = await run_monitoring_pipeline(db, server)
        results.append(
            CheckRunResponse(
                server_id=server.id,
                server_name=server.name,
                status=result["status"],
                status_code=result["status_code"],
                response_time_ms=result["response_time_ms"],
                message=result["message"],
                checked_at=now,
            )
        )

    # 상태별 집계
    up_count = sum(1 for r in results if r.status == "UP")
    slow_count = sum(1 for r in results if r.status == "SLOW")
    down_count = sum(1 for r in results if r.status == "DOWN")

    return CheckRunAllResponse(
        total=len(results),
        up=up_count,
        slow=slow_count,
        down=down_count,
        results=results,
    )


@router.get("/history/{server_id}", response_model=list[CheckResultResponse])
def get_check_history(
    server_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """특정 서버의 점검 이력을 조회합니다."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다")

    records = (
        db.query(CheckResult)
        .filter(CheckResult.server_id == server_id)
        .order_by(CheckResult.checked_at.desc())
        .limit(limit)
        .all()
    )

    # server_name을 추가하여 반환
    return [
        CheckResultResponse(
            id=r.id,
            server_id=r.server_id,
            server_name=server.name,
            status=r.status,
            status_code=r.status_code,
            response_time_ms=r.response_time_ms,
            message=r.message,
            checked_at=r.checked_at,
        )
        for r in records
    ]
