"""Ініціалізація логування для модуля."""
from __future__ import annotations

import logging
from typing import Optional

LOGGER_NAME = "imscheduler"


def get_logger() -> logging.Logger:
    """Повертає налаштований логер."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def configure_logging(level: Optional[str] = None) -> None:
    """Дозволяє динамічно змінити рівень логування."""
    logger = get_logger()
    if level:
        logger.setLevel(level.upper())
