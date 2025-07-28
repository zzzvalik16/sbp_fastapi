"""
Endpoints для обработки webhook уведомлений v1
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
import structlog

from app.api.dependencies import get_payment_service
from app.core.config import get_settings
from app.schemas.payment import WebhookPaymentData
from app.services.payment_service import PaymentService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "/payment",
    status_code=status.HTTP_200_OK,
    summary="Webhook уведомления о платежах",
    description="Обработка webhook уведомлений от Сбербанка о статусе платежей"
)
async def handle_payment_webhook(
    request: Request,
    webhook_data: WebhookPaymentData,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)]
) -> dict[str, str]:
    """
    Обработка webhook уведомления о платеже
    
    Args:
        request: HTTP запрос
        webhook_data: Данные webhook уведомления
        payment_service: Сервис для работы с платежами
        
    Returns:
        dict: Подтверждение обработки
        
    Raises:
        HTTPException: При ошибке валидации webhook
    """
    try:
        logger.info(
            "Received webhook payment notification",
            order_id=webhook_data.order_id,
            status=webhook_data.status,
            error_code=webhook_data.error_code,
            user_agent=request.headers.get("User-Agent"),
            remote_addr=request.client.host if request.client else None
        )
        
        # Валидация webhook подписи (если настроена)
        if not await _validate_webhook_signature(request, webhook_data):
            logger.warning("Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Обработка уведомления о платеже
        await payment_service.process_webhook_payment(
            md_order=webhook_data.mdOrder,
            order_number=webhook_data.orderNumber,
            operation=webhook_data.operation,
            status=webhook_data.status,
            additional_params=webhook_data.additionalParams
        )
        
        logger.info(
            "Webhook processed successfully",
            md_order=webhook_data.mdOrder,
            order_number=webhook_data.orderNumber,
            operation=webhook_data.operation,
            callback_status=webhook_data.status,
            additional_params=webhook_data.additionalParams
        )
        
        return {"status": "success", "message": "Webhook processed"}
        
    except Exception as e:
        logger.error(
            "Failed to process webhook",
            md_order=webhook_data.mdOrder,
            order_number=webhook_data.orderNumber,
            operation=webhook_data.operation,
            status=webhook_data.status,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


async def _validate_webhook_signature(
    request: Request,
    webhook_data: WebhookPaymentData
) -> bool:
    """
    Валидация подписи webhook уведомления
    
    Args:
        request: HTTP запрос
        webhook_data: Данные webhook
        
    Returns:
        bool: True если подпись валидна
    """
    settings = get_settings()
    
    # Если секрет не настроен, пропускаем валидацию
    if not settings.WEBHOOK_SECRET:
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
        settings.WEBHOOK_SECRET.encode(),
        json.dumps(webhook_data.dict(), sort_keys=True).encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)