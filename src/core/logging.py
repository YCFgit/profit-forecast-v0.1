"""日志配置"""

import sys

from loguru import logger

from src.core.config import get_settings


def setup_logging():
    settings = get_settings()
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level, format="{time:HH:mm:ss} | {level:<7} | {message}")
    logger.add(
        settings.log_file,
        level="INFO",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )
    return logger
