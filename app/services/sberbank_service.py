"""
Сервис для работы с API Сбербанка
"""

from typing import Any, Dict
import asyncio

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
            timeout=30.0,
            verify=False,
            http2=False
        )
        self.max_retries = 3
        self.retry_delay = 1.0

    async def _make_request_with_retry(
        self,
        method: str,
        url: str,
        json_data: Dict[str, Any],
        operation_name: str
    ) -> Dict[str, Any]:
        """
        Выполнить HTTP запрос с retry логикой

        Args:
            method: HTTP метод (post, get)
            url: URL для запроса
            json_data: JSON данные
            operation_name: Имя операции для логирования

        Returns:
            Dict[str, Any]: Ответ от API

        Raises:
            SberbankAPIException: При ошибке
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                if method.lower() == "post":
                    response = await self.client.post(url, json=json_data)
                else:
                    response = await self.client.get(url, params=json_data)

                response.raise_for_status()
                result = response.json()
                result = self._filter_null_values(result)
                return result

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"{operation_name} timeout, retrying",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        wait_time=wait_time
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise SberbankAPIException(f"Request timed out after {self.max_retries} retries")

            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"{operation_name} connection error, retrying",
                        error_type=type(e).__name__,
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        wait_time=wait_time
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise SberbankAPIException(
                        f"Network error: {type(e).__name__} after {self.max_retries} retries"
                    )

            except httpx.HTTPStatusError as e:
                raise SberbankAPIException(
                    f"HTTP error {e.response.status_code}: {e.response.text[:200]}"
                )

            except json.JSONDecodeError:
                raise SberbankAPIException(f"Invalid JSON response from Sberbank")

            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"{operation_name} request error, retrying",
                        error_type=type(e).__name__,
                        attempt=attempt + 1,
                        wait_time=wait_time
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise SberbankAPIException(f"Network error: {type(e).__name__}")

        raise SberbankAPIException(f"Failed after {self.max_retries} retries: {str(last_error)}")

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
        timeout_value = 1800
        if source_payments == "sbpClient":
            timeout_value = self.qr_timeout_secs

        url = f"{self.base_url}/register.do"
        json_dop_params = {
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
            "jsonParams": json_dop_params
        }

        if email and email.strip():
            data["email"] = email.strip()

        try:
            logger.info(
                "Creating QR code",
                order_number=order_number,
                amount=amount,
                url=url,
                description=description,
                email=email,
                source_payments=source_payments,
                sessionTimeoutSecs=timeout_value
            )

            result = await self._make_request_with_retry(
                "post",
                url,
                data,
                "create_qr_code"
            )

            if result.get("errorCode") != "0":
                logger.error(
                    "QR code create error",
                    order_id=result.get("orderId"),
                    error_code=result.get("errorCode"),
                    error_message=result.get("errorMessage")
                )
                raise SberbankAPIException(
                    f"Sberbank API error: {result.get('errorMessage', 'Unknown error')}",
                    details=result
                )

            logger.debug(
                "QR code created successfully",
                order_id=result.get("orderId")
            )

            return result

        except SberbankAPIException:
            raise

        except BaseException as e:
            logger.error(
                "Unexpected error creating QR code",
                order_number=order_number,
                error_type=type(e).__name__,
                error=str(e),
                traceback=traceback.format_exc()
            )
            raise SberbankAPIException(f"Unexpected error: {type(e).__name__}")

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

            result = await self._make_request_with_retry(
                "post",
                url,
                data,
                "get_payment_status"
            )

            logger.debug("Payment status retrieved", order_id=order_id)

            return result

        except SberbankAPIException:
            raise

        except Exception as e:
            logger.error(
                "Unexpected error getting payment status",
                order_id=order_id,
                error_type=type(e).__name__,
                error=str(e)
            )
            raise SberbankAPIException(f"Unexpected error: {type(e).__name__}")

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

            result = await self._make_request_with_retry(
                "post",
                url,
                data,
                "cancel_payment"
            )

            logger.info("Payment cancelled", order_id=order_id)

            return result

        except SberbankAPIException:
            raise

        except Exception as e:
            logger.error(
                "Unexpected error cancelling payment",
                order_id=order_id,
                error_type=type(e).__name__
            )
            raise SberbankAPIException(f"Unexpected error: {type(e).__name__}")

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
            logger.debug("Refunding payment", order_id=order_id, amount=amount)

            result = await self._make_request_with_retry(
                "post",
                url,
                data,
                "refund_payment"
            )

            logger.info("Payment refunded", order_id=order_id, amount=amount)

            return result

        except SberbankAPIException:
            raise

        except Exception as e:
            logger.error(
                "Unexpected error refunding payment",
                order_id=order_id,
                error_type=type(e).__name__
            )
            raise SberbankAPIException(f"Unexpected error: {type(e).__name__}")

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
