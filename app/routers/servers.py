"""OpsWatch 서버 관리 API 라우터."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.logging_config import get_logger
from app.models import Server
from app.schemas import ServerCreate, ServerResponse, ServerUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/servers", tags=["Servers"])


@router.post("", response_model=ServerResponse, status_code=201)
def create_server(server_data: ServerCreate, db: Session = Depends(get_db)):
    """새로운 점검 대상 서버를 등록합니다."""
    # 이름 중복 검사
    existing = db.query(Server).filter(Server.name == server_data.name).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"서버 이름 '{server_data.name}'이(가) 이미 존재합니다",
        )

    server = Server(
        name=server_data.name,
        url=server_data.url,
        description=server_data.description,
        importance=server_data.importance.value,
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    logger.info("SERVER_CREATED | id=%d | name=%s | url=%s", server.id, server.name, server.url)
    return server


@router.get("", response_model=list[ServerResponse])
def list_servers(db: Session = Depends(get_db)):
    """등록된 서버 목록을 조회합니다."""
    return db.query(Server).all()


@router.get("/{server_id}", response_model=ServerResponse)
def get_server(server_id: int, db: Session = Depends(get_db)):
    """특정 서버의 상세 정보를 조회합니다."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다")
    return server


@router.put("/{server_id}", response_model=ServerResponse)
def update_server(server_id: int, server_data: ServerUpdate, db: Session = Depends(get_db)):
    """서버 정보를 수정합니다."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다")

    update_fields = server_data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        if field == "importance" and value is not None:
            value = value.value  # Enum -> string
        setattr(server, field, value)

    server.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(server)
    return server


@router.delete("/{server_id}", status_code=204)
def delete_server(server_id: int, db: Session = Depends(get_db)):
    """서버를 삭제합니다."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다")

    db.delete(server)
    db.commit()
    logger.info("SERVER_DELETED | id=%d | name=%s", server.id, server.name)
