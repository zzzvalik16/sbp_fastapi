"""
Обработка исключений и ошибок
"""

from typing import Any, Dict

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = structlog.get_logger(__name__)


class SBPAPIException(Exception):
    """Базовое исключение для СБП API"""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Dict[str, Any] | None = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class PaymentException(SBPAPIException):
    """Исключения связанные с платежами"""
    pass


class SberbankAPIException(SBPAPIException):
    """Исключения при работе с API Сбербанка"""
    pass


class AtolException(SBPAPIException):
    """Исключения при работе с АТОЛ"""
    pass


class ValidationException(SBPAPIException):
    """Исключения валидации данных"""
    
    def __init__(self, message: str, field_errors: Dict[str, str] | None = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"field_errors": field_errors or {}}
        )


async def sbp_exception_handler(request: Request, exc: SBPAPIException) -> JSONResponse:
    """
    Обработчик исключений СБП API

    Args:
        request: HTTP запрос
        exc: Исключение СБП API

    Returns:
        JSONResponse: JSON ответ с ошибкой
    """
    logger.error(
        "SBP API Exception",
        path=request.url.path,
        method=request.method,
        error=exc.message
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message
        }
    )


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Обработчик ошибок валидации Pydantic

    Args:
        request: HTTP запрос
        exc: Ошибка валидации

    Returns:
        JSONResponse: JSON ответ с ошибкой валидации
    """
    logger.error(
        "Validation Error",
        path=request.url.path,
        method=request.method
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation failed"
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Обработчик HTTP исключений

    Args:
        request: HTTP запрос
        exc: HTTP исключение

    Returns:
        JSONResponse: JSON ответ с ошибкой
    """
    logger.error(
        "HTTP Exception",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Request failed"
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Общий обработчик исключений

    Args:
        request: HTTP запрос
        exc: Исключение

    Returns:
        JSONResponse: JSON ответ с ошибкой
    """
    logger.error(
        "Unhandled Exception",
        path=request.url.path,
        method=request.method
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error"
        }
    )


def add_exception_handlers(app: FastAPI) -> None:
    """
    Добавление обработчиков исключений в приложение
    
    Args:
        app: Экземпляр FastAPI приложения
    """
    app.add_exception_handler(SBPAPIException, sbp_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)