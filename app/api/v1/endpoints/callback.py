"""
Endpoints для обработки callback уведомлений v1
"""

import json
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.dependencies import get_payment_service
from app.api.dependencies import get_payment_service_safe
from app.core.config import get_settings
from app.core.database import get_db_safe
from app.models.payment import CallbackLog
from app.schemas.payment import CallbackPaymentData
from app.services.payment_service import PaymentService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Callback уведомления о платежах",
    description="Обработка callback уведомлений от Сбербанка о статусе платежей"
)
async def handle_payment_callback(
    request: Request,
    payment_service: Annotated[PaymentService, Depends(get_payment_service_safe)],
    db: Annotated[AsyncSession, Depends(get_db_safe)]
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
            logger.error("Invalid JSON format", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON format"
            )
        
        remote_addr = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

        logger.info(
            "Callback received",
            remote_addr=remote_addr
        )

        # Извлекаем данные из JSON с обработкой различных форматов
        md_order = json_data.get("mdOrder") or json_data.get("md_order")
        order_number = json_data.get("orderNumber") or json_data.get("order_number")
        operation = json_data.get("operation")
        callback_status = json_data.get("status")
        additional_params = json_data.get("additionalParams") or json_data.get("additional_params") or {}
        
        # Валидация обязательных полей
        if not md_order:
            logger.error("Missing mdOrder")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing mdOrder field"
            )

        if not order_number:
            logger.error("Missing orderNumber")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing orderNumber field"
            )

        if not operation:
            logger.error("Missing operation")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing operation field"
            )

        if callback_status is None:
            logger.error("Missing status")
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
            logger.error("Invalid callback data", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid callback data: {str(e)}"
            )
        
        # Сохраняем callback в базу данных
        callback_log = CallbackLog(
            md_order=callback_data.mdOrder,
            order_number=callback_data.orderNumber,
            operation=callback_data.operation,
            status=callback_data.status,
            additional_params=json.dumps(callback_data.additionalParams) if callback_data.additionalParams else None,
            remote_addr=remote_addr,
            user_agent=user_agent,
            processed=0
        )
        db.add(callback_log)
        await db.flush()

        # Валидация callback подписи (если настроена)
        if not await _validate_callback_signature(request, json_data):
            logger.warning("Invalid signature")

        # Обработка уведомления о платеже
        await payment_service.process_callback_payment(
            md_order=callback_data.mdOrder,
            order_number=callback_data.orderNumber,
            operation=callback_data.operation,
            status=callback_data.status,
            additional_params=callback_data.additionalParams
        )
        
        # Помечаем callback как обработанный
        callback_log.processed = 1
        await db.commit()

        logger.info(
            "Callback processed",
            md_order=callback_data.mdOrder
        )

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
