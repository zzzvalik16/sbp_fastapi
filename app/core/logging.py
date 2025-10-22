"""
Настройка логирования
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """
    Настройка структурированного логирования с ежедневной ротацией

    Args:
        log_level: Уровень логирования
    """
    # Создание директории для логов
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Настройка файлового логирования с ротацией
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Настройка консольного логирования
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # Настройка стандартного логирования
    logging.basicConfig(
        format="%(message)s",
        handlers=[console_handler, file_handler],
        level=getattr(logging, log_level.upper()),
    )

    # Настройка structlog с упрощенным выводом
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if sys.stdout.isatty() else structlog.processors.JSONRenderer()
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