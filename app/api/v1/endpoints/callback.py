"""
Endpoints для обработки callback уведомлений v1
"""

from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
import structlog

from app.api.dependencies import get_payment_service_safe
from app.core.config import get_settings
from app.schemas.payment import CallbackPaymentData
from app.services.payment_service import PaymentService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "/callback",
    status_code=status.HTTP_200_OK,
    summary="Callback уведомления о платежах",
    description="Обработка callback уведомлений от Сбербанка о статусе платежей"
)
async def handle_payment_callback(
    callback_data: CallbackPaymentData,
    payment_service: Annotated[PaymentService, Depends(get_payment_service_safe)],
    request: Request
) -> dict[str, str]:
    """
    Обработка callback уведомления о платеже
    
    Args:
        request: HTTP запрос
        payment_service: Сервис для работы с платежами
        
    Returns:
        dict: Подтверждение обработки
        
    Raises:
        HTTPException: При ошибке валидации callback
    """
    try:
        logger.info("Callback received", md_order=callback_data.mdOrder)

        # Обработка уведомления о платеже
        await payment_service.process_callback_payment(
            md_order=callback_data.mdOrder,
            order_number=callback_data.orderNumber,
            operation=callback_data.operation,
            status=callback_data.status,
            additional_params=callback_data.additionalParams
        )
        
        logger.info("Callback processed", md_order=callback_data.mdOrder)

        return {"status": "success", "message": "Callback processed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Callback processing failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process callback"
        )


async def _validate_callback_signature(
    request: Request,
    json_data: Dict[str, Any]
) -> bool:
    """
    Валидация подписи callback уведомления
    
    Args:
        request: HTTP запрос
        json_data: Данные callback
        
    Returns:
        bool: True если подпись валидна или проверка отключена
    """
    settings = get_settings()
    
    # Если секрет не настроен, пропускаем валидацию
    if not settings.CALLBACK_SECRET:
        return True

    signature = request.headers.get("X-Signature")
    if not signature:
        logger.warning("No signature header")
        return False

    # Проверка подписи HMAC SHA256
    import hmac
    import hashlib
    import json

    try:
        expected_signature = hmac.new(
            settings.CALLBACK_SECRET.encode(),
            json.dumps(json_data, sort_keys=True, separators=(',', ':')).encode(),
            hashlib.sha256
        ).hexdigest()

        is_valid = hmac.compare_digest(signature, expected_signature)

        if not is_valid:
            logger.warning("Signature mismatch")

        return is_valid

    except Exception as e:
        logger.error("Signature validation error", error=str(e))
        return False
