"""
Настройка логирования
"""

import logging
import sys
from typing import Any, Dict

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """
    Настройка структурированного логирования
    
    Args:
        log_level: Уровень логирования
    """
    # Настройка стандартного логирования
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Настройка structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Получение логгера с заданным именем
    
    Args:
        name: Имя логгера
        
    Returns:
        structlog.BoundLogger: Настроенный логгер
    """
    return structlog.get_logger(name)