import os
import sys
from pathlib import Path

from loguru import logger

log_dir = Path(os.getenv("LOG_DIR", "./data/logs"))
log_dir.mkdir(parents=True, exist_ok=True)

logger.remove()

logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)

logger.add(
    log_dir / "runner.log",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
    level="DEBUG",
)
