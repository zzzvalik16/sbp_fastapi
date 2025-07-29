"""
Конфигурация базы данных SQLAlchemy
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

settings = get_settings()

# Создание асинхронного движка
engine = create_async_engine(
    settings.database_url.replace("mysql+pymysql://", "mysql+aiomysql://"),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Создание фабрики сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей SQLAlchemy"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для получения сессии базы данных
    
    Yields:
        AsyncSession: Сессия базы данных
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error("Database session error", error=str(e), exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_safe() -> AsyncGenerator[AsyncSession, None]:
    """
    Безопасная версия dependency для получения сессии базы данных
    Используется в callback endpoints где важна стабильность
    
    Yields:
        AsyncSession: Сессия базы данных
    """
    session = None
    try:
        session = AsyncSessionLocal()
        yield session
        await session.commit()
    except Exception as e:
        logger.error("Database session error", error=str(e), exc_info=True)
        if session:
            await session.rollback()
        raise
    finally:
        if session:
            await session.close()


async def init_db() -> None:
    """
    Инициализация базы данных
    """
    try:
        async with engine.begin() as conn:
            # Создание всех таблиц
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise