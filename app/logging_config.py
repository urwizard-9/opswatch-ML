"""OpsWatch 로깅 설정 모듈.

구조화된 로그 포맷과 핸들러를 설정합니다.
이벤트명 기반으로 로그를 출력하여 운영 시 추적을 용이하게 합니다.
"""

import logging
import sys

from app.config import settings

# 로그 포맷: 타임스탬프 | 레벨 | 파일:라인 (함수) | 메시지
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(filename)s:%(lineno)d (%(funcName)s) | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """애플리케이션 전체 로깅을 설정합니다."""
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    root_logger.addHandler(console_handler)

    # uvicorn 로거 레벨 조정 (너무 시끄러운 로그 억제)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """모듈별 로거를 반환합니다.

    Args:
        name: 로거 이름 (보통 __name__ 전달)

    Returns:
        설정된 Logger 인스턴스
    """
    return logging.getLogger(name)
