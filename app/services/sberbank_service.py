"""
Сервис для работы с API Сбербанка
"""

from typing import Any, Dict

import httpx
import structlog

from app.core.config import get_settings
from app.core.exceptions import SberbankAPIException

logger = structlog.get_logger(__name__)


class SberbankService:
    """
    Сервис для взаимодействия с API Сбербанка
    """
    
    def __init__(self):
        """Инициализация сервиса Сбербанка"""
        self.settings = get_settings()
        self.base_url = self.settings.sberbank_api_url
        self.username = self.settings.SBERBANK_USERNAME
        self.password = self.settings.SBERBANK_PASSWORD
        self.return_url = self.settings.SBERBANK_RETURN_URL
        
        self.client = httpx.AsyncClient(
            timeout=30.0,
            verify=False
        )
    
    async def create_qr_code(
        self,
        order_number: str,
        amount: int,
        description: str,
        email: str
    ) -> Dict[str, Any]:
        """
        Создание динамического QR кода СБП
        
        Args:
            order_number: Уникальный номер заказа
            amount: Сумма в копейках
            description: Описание заказа
            email: Email плательщика
            
        Returns:
            Dict[str, Any]: Ответ от API Сбербанка
            
        Raises:
            SberbankAPIException: При ошибке API Сбербанка
        """
        url = f"{self.base_url}/register.do"
        
        data = {
            "userName": self.username,
            "password": self.password,
            "orderNumber": order_number,
            "amount": amount,
            "returnUrl": self.return_url,
            "description": description,
            "email": email,
            "jsonParams": {
                "qrType": "DYNAMIC_QR_SBP",
                "sbp.scenario": "C2B"
            }
        }
        
        try:
            logger.info(
                "Creating QR code",
                order_number=order_number,
                amount=amount,
                url=url
            )
            
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # Фильтрация null значений из ответа
            result = self._filter_null_values(result)
            
            logger.info(
                "QR code created successfully",
                order_number=order_number,
                order_id=result.get("orderId"),
                error_code=result.get("errorCode")
            )
            
            if result.get("errorCode") != "0":
                raise SberbankAPIException(
                    f"Sberbank API error: {result.get('errorMessage', 'Unknown error')}",
                    details=result
                )
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error creating QR code",
                order_number=order_number,
                error=str(e)
            )
            raise SberbankAPIException(f"HTTP error: {str(e)}")
        except Exception as e:
            logger.error(
                "Unexpected error creating QR code",
                order_number=order_number,
                error=str(e)
            )
            raise SberbankAPIException(f"Unexpected error: {str(e)}")
    
    async def get_payment_status(self, order_id: str) -> Dict[str, Any]:
        """
        Получение статуса платежа
        
        Args:
            order_id: ID заказа в Сбербанке
            
        Returns:
            Dict[str, Any]: Статус платежа
            
        Raises:
            SberbankAPIException: При ошибке API Сбербанка
        """
        url = f"{self.base_url}/getOrderStatusExtended.do"
        
        data = {
            "userName": self.username,
            "password": self.password,
            "orderId": order_id
        }
        
        try:
            logger.info("Getting payment status", order_id=order_id, url=url)
            
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # Фильтрация null значений из ответа
            result = self._filter_null_values(result)
            
            logger.info(
                "Payment status retrieved",
                order_id=order_id,
                order_status=result.get("orderStatus"),
                error_code=result.get("errorCode")
            )
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error getting payment status",
                order_id=order_id,
                error=str(e)
            )
            raise SberbankAPIException(f"HTTP error: {str(e)}")
        except Exception as e:
            logger.error(
                "Unexpected error getting payment status",
                order_id=order_id,
                error=str(e)
            )
            raise SberbankAPIException(f"Unexpected error: {str(e)}")
    
    async def cancel_payment(self, order_id: str) -> Dict[str, Any]:
        """
        Отмена платежа
        
        Args:
            order_id: ID заказа в Сбербанке
            
        Returns:
            Dict[str, Any]: Результат отмены
            
        Raises:
            SberbankAPIException: При ошибке API Сбербанка
        """
        url = f"{self.base_url}/reverse.do"
        
        data = {
            "userName": self.username,
            "password": self.password,
            "orderId": order_id
        }
        
        try:
            logger.info("Cancelling payment", order_id=order_id, url=url)
            
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # Фильтрация null значений из ответа
            result = self._filter_null_values(result)
            
            logger.info(
                "Payment cancelled",
                order_id=order_id,
                error_code=result.get("errorCode")
            )
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error cancelling payment",
                order_id=order_id,
                error=str(e)
            )
            raise SberbankAPIException(f"HTTP error: {str(e)}")
        except Exception as e:
            logger.error(
                "Unexpected error cancelling payment",
                order_id=order_id,
                error=str(e)
            )
            raise SberbankAPIException(f"Unexpected error: {str(e)}")
    
    async def refund_payment(self, order_id: str, amount: int) -> Dict[str, Any]:
        """
        Возврат платежа
        
        Args:
            order_id: ID заказа в Сбербанке
            amount: Сумма возврата в копейках
            
        Returns:
            Dict[str, Any]: Результат возврата
            
        Raises:
            SberbankAPIException: При ошибке API Сбербанка
        """
        url = f"{self.base_url}/refund.do"
        
        data = {
            "userName": self.username,
            "password": self.password,
            "orderId": order_id,
            "amount": amount
        }
        
        try:
            logger.info(
                "Refunding payment",
                order_id=order_id,
                amount=amount,
                url=url
            )
            
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # Фильтрация null значений из ответа
            result = self._filter_null_values(result)
            
            logger.info(
                "Payment refunded",
                order_id=order_id,
                amount=amount,
                error_code=result.get("errorCode")
            )
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error refunding payment",
                order_id=order_id,
                error=str(e)
            )
            raise SberbankAPIException(f"HTTP error: {str(e)}")
        except Exception as e:
            logger.error(
                "Unexpected error refunding payment",
                order_id=order_id,
                error=str(e)
            )
            raise SberbankAPIException(f"Unexpected error: {str(e)}")
    
    def _filter_null_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Фильтрация null значений из словаря
        
        Args:
            data: Исходный словарь
            
        Returns:
            Dict[str, Any]: Словарь без null значений
        """
        if isinstance(data, dict):
            return {
                key: self._filter_null_values(value) 
                for key, value in data.items() 
                if value is not None
            }
        elif isinstance(data, list):
            return [self._filter_null_values(item) for item in data if item is not None]
        else:
            return data
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.aclose()