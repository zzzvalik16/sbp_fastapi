"""
Endpoints для обработки callback уведомлений v1
"""

from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
import structlog

from app.api.dependencies import get_payment_service
from app.api.dependencies import get_payment_service_safe
from app.core.config import get_settings
from app.schemas.payment import CallbackPaymentData
from app.services.payment_service import PaymentService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Callback уведомления о платежах",
    description="Обработка callback уведомлений от Сбербанка о статусе платежей"
)
async def handle_payment_callback(
    request: Request,
    payment_service: Annotated[PaymentService, Depends(get_payment_service_safe)]
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
        # Получаем raw данные из запроса
        raw_body = await request.body()
        
        # Пытаемся получить JSON данные
        try:
            json_data = await request.json()
        except Exception as e:
            logger.error("Failed to parse JSON from callback", error=str(e), raw_body=raw_body.decode())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON format"
            )
        
        logger.info(
            "Received callback payment notification",
            json_data=json_data,
            user_agent=request.headers.get("User-Agent"),
            remote_addr=request.client.host if request.client else None
        )
        
        # Извлекаем данные из JSON с обработкой различных форматов
        md_order = json_data.get("mdOrder") or json_data.get("md_order")
        order_number = json_data.get("orderNumber") or json_data.get("order_number")
        operation = json_data.get("operation")
        callback_status = json_data.get("status")
        additional_params = json_data.get("additionalParams") or json_data.get("additional_params") or {}
        
        # Валидация обязательных полей
        if not md_order:
            logger.error("Missing mdOrder in callback", json_data=json_data)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing mdOrder field"
            )
        
        if not order_number:
            logger.error("Missing orderNumber in callback", json_data=json_data)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing orderNumber field"
            )
        
        if not operation:
            logger.error("Missing operation in callback", json_data=json_data)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing operation field"
            )
        
        if callback_status is None:
            logger.error("Missing status in callback", json_data=json_data)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing status field"
            )
        
        # Создаем объект для валидации
        try:
            callback_data = CallbackPaymentData(
                mdOrder=str(md_order),
                orderNumber=str(order_number),
                operation=str(operation),
                status=int(callback_status),
                additionalParams=additional_params
            )
        except Exception as e:
            logger.error("Failed to validate callback data", error=str(e), json_data=json_data)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid callback data: {str(e)}"
            )
        
        # Валидация callback подписи (если настроена)
        if not await _validate_callback_signature(request, json_data):
            logger.warning("Invalid callback signature", json_data=json_data)
            # Не блокируем обработку, только логируем предупреждение
        
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
            callback_status=callback_data.status
        )
        
        return {"status": "success", "message": "Callback processed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to process callback",
            error=str(e),
            json_data=json_data if 'json_data' in locals() else None
        )
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
        logger.info("Callback signature validation disabled (no secret configured)")
        return True
    
    signature = request.headers.get("X-Signature")
    if not signature:
        logger.warning("No signature header found")
        return False
    
    # Здесь должна быть реализация проверки подписи
    # В зависимости от алгоритма, используемого Сбербанком
    # Пример для HMAC SHA256:
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
            logger.warning(
                "Invalid callback signature",
                expected=expected_signature,
                received=signature
            )
        
        return is_valid
        
    except Exception as e:
        logger.error("Error validating callback signature", error=str(e))
        return False