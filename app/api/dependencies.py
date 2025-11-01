"""
Зависимости для API endpoints
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_db_safe
from app.services.payment_service import PaymentService
from app.services.sberbank_service import SberbankService
from app.services.atol_service import AtolService


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
