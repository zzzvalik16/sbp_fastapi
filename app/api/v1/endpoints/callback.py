"""
Endpoints для обработки callback уведомлений v1
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
import structlog

from app.api.dependencies import get_payment_service
from app.core.config import get_settings
from app.schemas.payment import CallbackPaymentData
from app.services.payment_service import PaymentService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "/payment",
    status_code=status.HTTP_200_OK,
    summary="Callback уведомления о платежах",
    description="Обработка callback уведомлений от Сбербанка о статусе платежей"
)
async def handle_payment_callback(
    request: Request,
    callback_data: CallbackPaymentData,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)]
) -> dict[str, str]:
    """
    Обработка callback уведомления о платеже
    
    Args:
        request: HTTP запрос
        callback_data: Данные callback уведомления
        payment_service: Сервис для работы с платежами
        
    Returns:
        dict: Подтверждение обработки
        
    Raises:
        HTTPException: При ошибке валидации callback
    """
    try:
        logger.info(
            "Received callback payment notification",
            md_order=callback_data.mdOrder,
            order_number=callback_data.orderNumber,
            operation=callback_data.operation,
            status=callback_data.status,
            error_code=callback_data.additionalParams.get("errorCode") if callback_data.additionalParams else None,
            user_agent=request.headers.get("User-Agent"),
            remote_addr=request.client.host if request.client else None
        )
        
        # Валидация callback подписи (если настроена)
        if not await _validate_callback_signature(request, callback_data):
            logger.warning("Invalid callback signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid callback signature"
            )
        
        # Обработка уведомления о платеже
        await payment_service.process_callback_payment(
            md_order=callback_data.mdOrder,
            order_number=callback_data.orderNumber,
            operation=callback_data.operation,
            status=callback_data.status,
            additional_params=callback_data.additionalParams
        )
        
        logger.info(
            "Callback processed successfully",
            md_order=callback_data.mdOrder,
            order_number=callback_data.orderNumber,
            operation=callback_data.operation,
            callback_status=callback_data.status,
            additional_params=callback_data.additionalParams
        )
        
        return {"status": "success", "message": "Callback processed"}
        
    except Exception as e:
        logger.error(
            "Failed to process callback",
            md_order=callback_data.mdOrder,
            order_number=callback_data.orderNumber,
            operation=callback_data.operation,
            status=callback_data.status,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process callback"
        )


async def _validate_callback_signature(
    request: Request,
    callback_data: CallbackPaymentData
) -> bool:
    """
    Валидация подписи callback уведомления
    
    Args:
        request: HTTP запрос
        callback_data: Данные callback
        
    Returns:
        bool: True если подпись валидна
    """
    settings = get_settings()
    
    # Если секрет не настроен, пропускаем валидацию
    if not settings.CALLBACK_SECRET:
        return True
    
    signature = request.headers.get("X-Signature")
    if not signature:
        return False
    
    # Здесь должна быть реализация проверки подписи
    # В зависимости от алгоритма, используемого Сбербанком
    # Пример для HMAC SHA256:
    import hmac
    import hashlib
    import json
    
    expected_signature = hmac.new(
        settings.CALLBACK_SECRET.encode(),
        json.dumps(callback_data.model_dump(), sort_keys=True).encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)