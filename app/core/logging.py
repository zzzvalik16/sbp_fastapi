"""
Настройка логирования
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

import structlog


def setup_logging(log_level: str = "INFO", debug: bool = False) -> None:
    """
    Настройка структурированного логирования с ежедневной ротацией

    Args:
        log_level: Уровень логирования (WARNING по умолчанию)
        debug: Режим отладки для подробного вывода
    """
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Определяем уровень логирования
    level = logging.DEBUG if debug else getattr(logging, log_level.upper(), logging.WARNING)

    # Настройка файлового логирования с ротацией
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(level)

    if debug:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    file_handler.setFormatter(file_formatter)

    # Настройка консольного логирования
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if debug:
        console_formatter = logging.Formatter('%(levelname)s [%(name)s]: %(message)s')
    else:
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # Отключаем логи от библиотек
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Настройка стандартного логирования
    logging.basicConfig(
        format="%(message)s",
        handlers=[console_handler, file_handler],
        level=level,
        force=True
    )

    # Настройка structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.format_exc_info,
    ]

    if debug:
        processors.extend([
            structlog.stdlib.add_logger_name,
            structlog.processors.CallsiteParameterAdder(
                [structlog.processors.CallsiteParameter.FUNC_NAME]
            ),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        ])

    processors.append(
        structlog.dev.ConsoleRenderer() if sys.stdout.isatty() else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=processors,
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