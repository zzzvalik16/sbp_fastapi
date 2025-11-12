"""
Сервис для работы с API Сбербанка
"""

from typing import Any, Dict

import httpx
import structlog
import traceback
import json

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
        self.return_fail_url = self.settings.SBERBANK_FAIL_RETURN_URL        
        self.qr_timeout_secs = self.settings.SBERBANK_QR_TIMEOUT * 60
        
        self.client = httpx.AsyncClient(
            timeout=50.0,
            verify=False
        )
    
    async def create_qr_code(
        self,
        order_number: str,
        amount: int,
        description: str,
        email: str,
        source_payments: str
    ) -> Dict[str, Any]:
        """
        Создание динамического QR кода СБП
        
        Args:
            order_number: Уникальный номер заказа
            amount: Сумма в копейках
            description: Описание заказа
            email: Email плательщика
            source_payments: Источник запроса кода
            
        Returns:
            Dict[str, Any]: Ответ от API Сбербанка
            
        Raises:
            SberbankAPIException: При ошибке API Сбербанка
        """
        timeout_value = 86400 # По умолчанию
        if source_payments == "sbpClient":
            timeout_value = self.qr_timeout_secs

        url = f"{self.base_url}/register.do"
        jsonDopParams={
                "qrType": "DYNAMIC_QR_SBP",
                "sbp.scenario": "C2B"
            }
        data = {
            "userName": self.username,
            "password": self.password,
            "orderNumber": order_number,
            "amount": amount,
            "returnUrl": self.return_url,
            "failUrl": self.return_fail_url,
            "description": description, 
            "sessionTimeoutSecs": timeout_value,           
            "jsonParams": jsonDopParams
        }
       
        if email and email.strip():
            # Здесь email — это строка, содержащая хотя бы один символ, кроме пробелов
            data["email"] = email.strip()     
          
        try:
            logger.info(
                "Creating QR code",
                order_number=order_number,
                amount=amount,
                url=url,
                #jsonParams=jsonDopParams,
                description=description,
                email=email,
                source_payments=source_payments,
                sessionTimeoutSecs=timeout_value
            )
            
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # Фильтрация null значений из ответа
            result = self._filter_null_values(result)    
            
            if result.get("errorCode") != "0":
                logger.error(
                    "QR code create error",                    
                    order_id=result.get("orderId"),
                    result=result
                    #order_number=order_number,                    
                    #error_code=result.get("errorCode")
                )
                raise SberbankAPIException(
                    f"Sberbank API error: {result.get('errorMessage', 'Unknown error')}",
                    details=result
                )
            
            logger.debug(
                "QR code created successfully",
                order_id=result.get("orderId"),
                result=result                
                #order_number=order_number,                
                #error_code=result.get("errorCode")
            )
            
            return result

        except SberbankAPIException:
            raise

        except httpx.Timeout as e: # Специфично ловим таймаут
            logger.error(
                "Timeout creating QR code",
                order_number=order_number,
                error=f"Request timed out after {e.request.timeout} seconds. {str(e)}"
            )
            raise SberbankAPIException(f"Request timed out: {str(e)}")

        except httpx.HTTPStatusError as e: # Конкретнее ловим статусные ошибки (4xx, 5xx)
            logger.error(
                "HTTP status error creating QR code",
                order_number=order_number,
                error=f"Status Code: {e.response.status_code}, Response: {e.response.text}"
            )
            raise SberbankAPIException(f"HTTP status error: {e.response.status_code}")

        except httpx.RequestError as e: # Ловим ошибки запроса (сеть, DNS, таймаут)
            logger.error(
                "Request error creating QR code",
                order_number=order_number,
                error=str(e)
            )
            raise SberbankAPIException(f"Request error: {str(e)}")

        except json.JSONDecodeError as e: # Ловим ошибки парсинга JSON
            logger.error(
                "JSON decode error creating QR code",
                order_number=order_number,
                error=f"Could not decode JSON response: {str(e)}"
            )
            raise SberbankAPIException(f"Invalid JSON response")

        except Exception as e: # Ловим все остальные неожиданные ошибки
            logger.error(
                "Unexpected error creating QR code",
                order_number=order_number,
                error=str(e),
                traceback=traceback.format_exc()
            )
            raise SberbankAPIException(f"An unexpected error occurred: {str(e)}")       

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
            
            logger.debug(
                "Payment status retrieved",
                order_id=order_id,
                result=result
                #order_status=result.get("orderStatus"),
                #error_code=result.get("errorCode")                
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
        url = f"{self.base_url}/decline.do"
        
        data = {
            "userName": self.username,
            "password": self.password,
            "orderId": order_id
        }
        
        try:
            logger.debug("Cancelling payment", order_id=order_id, url=url)
            
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
            logger.debug(
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
                #result=result,
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
