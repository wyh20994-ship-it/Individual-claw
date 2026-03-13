"""
日志工具 — 基于 loguru
"""

import sys
from loguru import logger

# 移除默认 handler，自定义格式
logger.remove()

logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

logger.add(
    "../data/logs/runner.log",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
    level="DEBUG",
)
