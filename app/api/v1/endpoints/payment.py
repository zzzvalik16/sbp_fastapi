"""
Endpoints для работы с платежами v1
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_payment_service
from app.core.exceptions import PaymentException
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentStatusResponse,
    PaymentCancelResponse,
    PaymentRefundRequest,
    PaymentRefundResponse
)
from app.services.payment_service import PaymentService

router = APIRouter()


@router.post(
    "/create",
    response_model=PaymentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание платежа СБП",
    description="Создание нового платежа через Систему Быстрых Платежей"
)
async def create_payment(
    request: PaymentCreateRequest,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)]
) -> PaymentCreateResponse:
    """
    Создание нового платежа СБП
    
    Args:
        request: Данные для создания платежа
        payment_service: Сервис для работы с платежами
        
    Returns:
        PaymentCreateResponse: Результат создания платежа
        
    Raises:
        HTTPException: При ошибке создания платежа
    """
    try:
        return await payment_service.create_payment(request)
    except PaymentException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/status/{order_id}",
    response_model=PaymentStatusResponse,
    summary="Получение статуса платежа",
    description="Получение текущего статуса платежа по ID заказа в Сбербанке"
)
async def get_payment_status(
    order_id: str,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)]
) -> PaymentStatusResponse:
    """
    Получение статуса платежа
    
    Args:
        order_id: ID заказа в Сбербанке
        payment_service: Сервис для работы с платежами
        
    Returns:
        PaymentStatusResponse: Статус платежа
        
    Raises:
        HTTPException: При ошибке получения статуса
    """
    try:
        return await payment_service.get_payment_status(order_id)
    except PaymentException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/cancel/{order_id}",
    response_model=PaymentCancelResponse,
    summary="Отмена платежа",
    description="Отмена платежа в системе НСПК"
)
async def cancel_payment(
    order_id: str,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)]
) -> PaymentCancelResponse:
    """
    Отмена платежа
    
    Args:
        order_id: ID заказа в Сбербанке
        payment_service: Сервис для работы с платежами
        
    Returns:
        PaymentCancelResponse: Результат отмены платежа
        
    Raises:
        HTTPException: При ошибке отмены платежа
    """
    try:
        return await payment_service.cancel_payment(order_id)
    except PaymentException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/refund/{order_id}",
    response_model=PaymentRefundResponse,
    summary="Возврат платежа",
    description="Возврат платежа полностью или частично"
)
async def refund_payment(
    order_id: str,
    request: PaymentRefundRequest,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)]
) -> PaymentRefundResponse:
    """
    Возврат платежа
    
    Args:
        order_id: ID заказа в Сбербанке
        request: Данные для возврата
        payment_service: Сервис для работы с платежами
        
    Returns:
        PaymentRefundResponse: Результат возврата платежа
        
    Raises:
        HTTPException: При ошибке возврата платежа
    """
    try:
        return await payment_service.refund_payment(order_id, request.amount)
    except PaymentException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )