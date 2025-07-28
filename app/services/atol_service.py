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
        self.login = self.settings.ATOL_LOGIN
        self.password = self.settings.ATOL_PASSWORD
        self.url = self.settings.ATOL_URL
        
        self.client = httpx.AsyncClient(
            timeout=30.0,
            verify=False
        )
    
    async def send_fiscal_receipt(
        self,
        account: str,
        fid: int,
        rq_uid: str,
        amount: float,
        email: str,
        phone: Optional[str] = None
    ) -> dict:
        """
        Отправка фискального чека в АТОЛ
        
        Args:
            account: Номер лицевого счета
            fid: ID записи в таблице FEE
            rq_uid: Уникальный идентификатор запроса
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
                "payment_id": "SBP",
                "pin": account,
                "external_id": str(fid),
                "operation": "sell",
                "email": email,
                "receipt": [
                    {
                        "price": amount,
                        "quantity": 1.000
                    }
                ]
            }
            
            if phone:
                data["phone"] = phone
            
            logger.info(
                "Sending fiscal receipt",
                fid=fid,
                rq_uid=rq_uid,
                account=account,
                amount=amount,
                email=email
            )
            
            response = await self.client.post(self.url, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            logger.info(
                "Fiscal receipt sent successfully",
                fid=fid,
                rq_uid=rq_uid,
                response=result
            )
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error sending fiscal receipt",
                fid=fid,
                rq_uid=rq_uid,
                error=str(e)
            )
            raise AtolException(f"HTTP error sending fiscal receipt: {str(e)}")
        except Exception as e:
            logger.error(
                "Unexpected error sending fiscal receipt",
                fid=fid,
                rq_uid=rq_uid,
                error=str(e)
            )
            raise AtolException(f"Unexpected error sending fiscal receipt: {str(e)}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.aclose()