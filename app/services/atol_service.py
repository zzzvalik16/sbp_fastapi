"""
Сервис для фискализации через АТОЛ
"""

import hashlib
import time
from typing import Optional

import httpx
import structlog

from app.core.config import get_settings
from app.core.exceptions import AtolException

logger = structlog.get_logger(__name__)


class AtolService:
    """
    Сервис для отправки фискальных чеков через АТОЛ
    """
    
    def __init__(self):
        """Инициализация сервиса АТОЛ"""
        self.settings = get_settings()
        self.url = self.settings.ATOL_URL
        self.login = self.settings.ATOL_LOGIN
        self.password = self.settings.ATOL_PASSWORD
        self.payment_id = self.settings.ATOL_PAYMENT_ID
        
        self.client = httpx.AsyncClient(
            timeout=30.0,
            verify=True
        )
    
    async def send_fiscal_receipt(
        self,
        account: str,
        fid: int,
        order_id: str,
        amount: float,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> dict:
        """
        Отправка фискального чека в АТОЛ
        
        Args:
            account: Номер лицевого счета
            fid: ID записи в таблице FEE
            order_id: Уникальный идентификатор запроса
            amount: Сумма платежа
            email: Email для отправки чека
            phone: Телефон для отправки чека
            
        Returns:
            dict: Ответ от АТОЛ API
            
        Raises:
            AtolException: При ошибке отправки чека
        """
        try:
            timestamp = int(time.time())
            hash_string = hashlib.sha1(
                hashlib.md5(
                    f"{self.login}{self.password}{timestamp}".encode()
                ).hexdigest().encode()
            ).hexdigest()
            
            data = {
                "login": self.login,
                "hash": hash_string,
                "timestamp": timestamp,
                "payment_id": self.payment_id,
                "pin": account,
                "external_id": str(fid),
                "operation": "sell",                
                "receipt": [
                    {
                        "price": amount,
                        "quantity": 1.000
                    }
                ]
            }
            
            if email:
                data["email"] = email
            if phone:
                data["phone"] = phone
            
            logger.debug(
                "Sending fiscal receipt",
                order_id=order_id,
                fid=fid,                
                account=account,
                amount=amount,
                email=email
            )
            
            response = await self.client.post(self.url, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            logger.info(
                "Fiscal receipt sent successfully",
                order_id=order_id,
                fid=fid,                
                response=result
            )
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error sending fiscal receipt",
                order_id=order_id,
                fid=fid,                
                error=str(e)
            )
            raise AtolException(f"HTTP error sending fiscal receipt: {str(e)}")
        except Exception as e:
            logger.error(
                "Unexpected error sending fiscal receipt",
                order_id=order_id,
                fid=fid,                
                error=str(e)
            )
            raise AtolException(f"Unexpected error sending fiscal receipt: {str(e)}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.aclose()