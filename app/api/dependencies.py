"""
Зависимости для API endpoints
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db, get_db_safe
from app.services.payment_service import PaymentService
from app.services.sberbank_service import SberbankService
from app.services.atol_service import AtolService

logger = structlog.get_logger(__name__)

ALLOWED_CALLBACK_IPS = {
    "84.252.147.143",
    "185.157.97.241"
}


async def get_sberbank_service() -> SberbankService:
    """
    Dependency для получения сервиса Сбербанка
    
    Returns:
        SberbankService: Экземпляр сервиса
    """
    return SberbankService()


async def get_atol_service() -> AtolService:
    """
    Dependency для получения сервиса АТОЛ
    
    Returns:
        AtolService: Экземпляр сервиса
    """
    return AtolService()


async def get_payment_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    sberbank_service: Annotated[SberbankService, Depends(get_sberbank_service)],
    atol_service: Annotated[AtolService, Depends(get_atol_service)]
) -> PaymentService:
    """
    Dependency для получения сервиса платежей
    
    Args:
        db: Сессия базы данных
        sberbank_service: Сервис Сбербанка
        atol_service: Сервис АТОЛ
        
    Returns:
        PaymentService: Экземпляр сервиса платежей
    """
    return PaymentService(db, sberbank_service, atol_service)


async def get_payment_service_safe(
    db: Annotated[AsyncSession, Depends(get_db_safe)],
    sberbank_service: Annotated[SberbankService, Depends(get_sberbank_service)],
    atol_service: Annotated[AtolService, Depends(get_atol_service)]
) -> PaymentService:
    """
    Безопасная версия dependency для получения сервиса платежей
    Используется в callback endpoints

    Args:
        db: Безопасная сессия базы данных
        sberbank_service: Сервис Сбербанка
        atol_service: Сервис АТОЛ

    Returns:
        PaymentService: Экземпляр сервиса платежей
    """
    return PaymentService(db, sberbank_service, atol_service)


async def verify_callback_ip(request: Request) -> Request:
    """
    Проверка IP адреса для callback уведомлений

    Разрешены только запросы с определённых IP адресов Сбербанка

    Args:
        request: HTTP запрос

    Returns:
        Request: Исходный запрос, если проверка пройдена

    Raises:
        HTTPException: Если IP адрес не в списке разрешённых
    """
    client_ip = request.client.host if request.client else None

    if not client_ip:
        logger.warning("Unable to determine client IP address")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to verify client IP"
        )

    if client_ip not in ALLOWED_CALLBACK_IPS:
        logger.warning(
            "Callback request from unauthorized IP",
            client_ip=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    logger.info("Callback IP verified", client_ip=client_ip)
    return request
