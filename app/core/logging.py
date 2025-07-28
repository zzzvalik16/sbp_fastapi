"""
Настройка логирования
"""

import logging
import os
import sys
from typing import Any, Dict

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """
    Настройка структурированного логирования
    
    Args:
        log_level: Уровень логирования
    """
    # Создание директории для логов
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настройка файлового логирования
    file_handler = logging.FileHandler(
        os.path.join(log_dir, "app.log"),
        encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Настройка консольного логирования
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Настройка стандартного логирования
    logging.basicConfig(
        format="%(message)s",
        handlers=[console_handler, file_handler],
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