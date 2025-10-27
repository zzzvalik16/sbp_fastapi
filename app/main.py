"""
Главный модуль FastAPI приложения для работы с СБП
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.api.v2.router import api_v2_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.exceptions import add_exception_handlers
from app.core.logging import setup_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Управление жизненным циклом приложения
    
    Args:
        app: Экземпляр FastAPI приложения
        
    Yields:
        None: Контекст выполнения приложения
    """
    # Startup
    logger.warning("Starting SBP API")
    await init_db()

    yield

    # Shutdown
    logger.warning("Shutting down SBP API")


def create_app() -> FastAPI:
    """
    Создание и настройка FastAPI приложения

    Returns:
        FastAPI: Настроенное приложение
    """
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL, debug=settings.DEBUG)

    # Отключаем документацию в продакшене
    docs_url = "/docs" if settings.DEBUG else None
    redoc_url = "/redoc" if settings.DEBUG else None

    app = FastAPI(
        title="СБП API",
        description="API для работы с Системой Быстрых Платежей через Сбербанк",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        lifespan=lifespan
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handlers
    add_exception_handlers(app)
    
    # API routers
    app.include_router(api_v1_router, prefix="/api/v1")
    app.include_router(api_v2_router, prefix="/api/v2")
    
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Проверка состояния API"""
        return {"status": "healthy", "version": "1.0.0"}
    
    return app


app = create_app()