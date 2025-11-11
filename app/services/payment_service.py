"""
Сервис для работы с платежами
"""

import hashlib
import random
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PaymentException, ValidationException
from app.models.payment import PaymentLog, Fee, PaymentState
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentStatusResponse,
    PaymentCancelResponse,
    PaymentRefundResponse
)
from app.services.sberbank_service import SberbankService
from app.services.atol_service import AtolService

logger = structlog.get_logger(__name__)


class PaymentService:
    """
    Сервис для управления платежами СБП
    """
    
    def __init__(
        self,
        db: AsyncSession,
        sberbank_service: SberbankService,
        atol_service: AtolService
    ):
        """
        Инициализация сервиса платежей
        
        Args:
            db: Сессия базы данных
            sberbank_service: Сервис для работы с API Сбербанка
            atol_service: Сервис для фискализации АТОЛ
        """
        self.db = db
        self.sberbank_service = sberbank_service
        self.atol_service = atol_service
    
    async def create_payment(self, request: PaymentCreateRequest) -> PaymentCreateResponse:
        """
        Создание нового платежа СБП
        
        Args:
            request: Данные для создания платежа
            
        Returns:
            PaymentCreateResponse: Результат создания платежа
            
        Raises:
            PaymentException: При ошибке создания платежа
        """
        try:
            # Генерация уникального идентификатора запроса
            rq_uid = self._generate_rq_uid()  
            
            # Создание записи в базе данных
            payment_data = { 
                "uid": None,                             
                "account": request.account,
                "rq_uid": rq_uid,
                "order_sum": float(request.amount),
                "order_create_date": datetime.now(),
                "order_state": PaymentState.CREATED,
                "source_payments": request.paymentStat,                
                "rq_tm": datetime.now()
            }
            
            if request.phone:
                payment_data["fiscal_phone"] = request.phone

            if request.email:
                payment_data["fiscal_email"] = request.email    
            
            payment = await self._create_payment_log(payment_data)

            customer_uid = await self._get_customer_uid(request.account)
            if not customer_uid:                
                logger.error(
                    "User not found",
                    account=request.account,
                    rq_uid=rq_uid
                )
                update_data = {
                    "error_description": "Пользователь не найден", 
                    "order_state": PaymentState.DECLINED
                }
                                
                await self._update_payment_by_id(payment.sbp_id, update_data)
                return PaymentCreateResponse(
                    success=False,
                    sbp_id=payment.sbp_id,
                    rq_uid=rq_uid,
                    order_id=None,
                    qrcode_link="",
                    qr_url=None,
                    amount=request.amount,
                    status=PaymentState.DECLINED
                )
            
            # Создание QR кода через API Сбербанка
            sberbank_response = await self.sberbank_service.create_qr_code(
                order_number=str(payment.sbp_id),  # Используем sbp_id как orderNumber
                amount=int(request.amount * 100),  # Конвертация в копейки
                description=f"Пополнение лицевого счета №{request.account}",
                email=str(request.email)
            )
            
            # Обновление записи с данными от банка
            update_data = {
                "uid": customer_uid, 
                "error_code": sberbank_response.get("errorCode", "0"),
                "operation_date_time": datetime.now()
            }
            
            # Проверка на ошибки от Сбербанка
            if sberbank_response.get("errorCode") != "0":
                update_data["error_description"] = sberbank_response.get("errorMessage")
                update_data["order_state"] = PaymentState.DECLINED
                
                await self._update_payment_by_id(payment.sbp_id, update_data)
                
                logger.error(
                    "Sberbank API error during payment creation",
                    sbp_id=payment.sbp_id,
                    rq_uid=rq_uid,
                    error_code=sberbank_response.get("errorCode"),
                    error_message=sberbank_response.get("errorMessage")
                )
                
                return PaymentCreateResponse(
                    success=False,
                    sbp_id=payment.sbp_id,
                    rq_uid=rq_uid,
                    order_id=None,
                    qrcode_link="",
                    qr_url=None,
                    amount=request.amount,
                    status=PaymentState.DECLINED
                )
            
            # Извлечение sbpPayload из ответа при успешном создании
            sbp_payload = sberbank_response.get("externalParams", {}).get("sbpPayload")
            if not sbp_payload:
                update_data["error_description"] = "SBP payload not received from Sberbank"
                update_data["order_state"] = PaymentState.DECLINED
                
                await self._update_payment_by_id(payment.sbp_id, update_data)
                
                logger.error(
                    "SBP payload not received from Sberbank",
                    sbp_id=payment.sbp_id,
                    rq_uid=rq_uid,
                    sberbank_response=sberbank_response
                )
                
                return PaymentCreateResponse(
                    success=False,
                    sbp_id=payment.sbp_id,
                    rq_uid=rq_uid,
                    order_id=sberbank_response.get("orderId"),
                    qrcode_link="",
                    qr_url=None,
                    amount=request.amount,
                    status=PaymentState.DECLINED
                )
            
            # Успешное создание платежа
            update_data["order_form_url"] = sbp_payload
            if sberbank_response.get("orderId"):
                update_data["order_id"] = sberbank_response["orderId"]
            
            await self._update_payment_by_id(payment.sbp_id, update_data)
            
            logger.info(
                "Payment created successfully",
                order_id=sberbank_response.get("orderId"),
                sbp_id=payment.sbp_id,
                amount=request.amount
            )
            
            return PaymentCreateResponse(
                success=True,
                sbp_id=payment.sbp_id,
                rq_uid=rq_uid,
                order_id=sberbank_response.get("orderId"),
                qrcode_link=sbp_payload,
                qr_url=sberbank_response.get("formUrl"),
                amount=request.amount,
                status=PaymentState.CREATED if sberbank_response.get("errorCode") == "0" else PaymentState.DECLINED
            )
            
        except Exception as e:
            logger.error("Failed to create payment", error=str(e))
            raise PaymentException(f"Failed to create payment: {str(e)}")
    
    async def get_payment_status(self, order_id: str) -> PaymentStatusResponse:
        """
        Получение статуса платежа
        
        Args:
            order_id: ID заказа в Сбербанке
            
        Returns:
            PaymentStatusResponse: Статус платежа
            
        Raises:
            PaymentException: При ошибке получения статуса
        """
        try:
            # Поиск платежа в базе данных
            payment = await self._get_payment_by_order_id(order_id)
            if not payment:
                raise PaymentException("Payment not found")
            
            # Получение актуального статуса из API Сбербанка
            try:
                sberbank_status = await self.sberbank_service.get_payment_status(order_id)
                
                if sberbank_status.get("errorCode") == "0":
                    new_status = self._map_sberbank_status(
                        sberbank_status.get("orderStatus", 0)
                    )
                    update_data = {                           
                        "error_code": None,
                        "error_description": None
                    }
                    await self._update_payment_by_id(payment.sbp_id, update_data)

                    # Обновление статуса в базе, если он изменился
                    if payment.order_state != new_status:
                        update_data["order_state"] = new_status
                        
                        if sberbank_status.get("depositedDate"):
                            update_data["operation_date_time"] = datetime.fromtimestamp(
                                sberbank_status["depositedDate"] / 1000
                            )
                        
                        #await self._update_payment_by_id(payment.sbp_id, update_data)
                        payment.order_state = new_status
                        
                        # Обработка статуса PAID (orderStatus = 2)
                        #if new_status == PaymentState.PAID:
                            #await self._process_paid_payment(payment)
                            
            except Exception as e:
                logger.warning(
                    "Failed to get status from Sberbank API",
                    order_id=order_id,
                    error=str(e)
                )
            
            return PaymentStatusResponse(
                success=True,
                sbp_id=payment.sbp_id,
                rq_uid=payment.rq_uid,
                order_id=payment.order_id,
                status=payment.order_state,
                amount=Decimal(str(payment.order_sum)) if payment.order_sum else None,
                account=payment.account,
                created_at=payment.order_create_date,
                operation_time=payment.operation_date_time
            )
            
        except PaymentException:
            raise
        except Exception as e:
            logger.error("Failed to get payment status", order_id=order_id, error=str(e))
            raise PaymentException(f"Failed to get payment status: {str(e)}")
    
    async def cancel_payment(self, order_id: str) -> PaymentCancelResponse:
        """
        Отмена платежа
        
        Args:
            order_id: ID заказа в Сбербанке
            
        Returns:
            PaymentCancelResponse: Результат отмены платежа
            
        Raises:
            PaymentException: При ошибке отмены платежа
        """
        try:
            payment = await self._get_payment_by_order_id(order_id)
            if not payment:
                raise PaymentException("Payment not found")
            
            # Отмена платежа через API Сбербанка
            cancel_result = await self.sberbank_service.cancel_payment(order_id)
            
            if cancel_result.get("errorCode") != "0":
                error_msg = cancel_result.get("errorMessage", "Unknown error")
                error_code = cancel_result.get("errorCode")
                
                await self._update_payment_by_id(
                    payment.sbp_id,
                    {
                        "order_state": PaymentState.DECLINED,
                        "error_code": error_code,
                        "error_description": error_msg,
                        "operation_date_time": datetime.now()
                    }
                )
                
                logger.error(
                    "Failed to cancel payment via Sberbank API",
                    order_id=order_id,
                    error_code=error_code,
                    error_message=error_msg,
                    #result=cancel_result
                )
                
                #raise PaymentException(f"Failed to cancel payment: {error_msg}")
            
            # Обновление статуса в базе
            await self._update_payment_by_id(
                payment.sbp_id,
                {
                    "order_state": PaymentState.DECLINED,
                    "operation_date_time": datetime.now()
                }
            )
            
            logger.info("Payment cancelled successfully", order_id=order_id, result=cancel_result)
            
            return PaymentCancelResponse(
                success=True,
                sbp_id=payment.sbp_id,
                order_id=order_id,
                status=PaymentState.DECLINED,
                message="Payment cancelled successfully"
            )
            
        except PaymentException:
            raise
        except Exception as e:
            logger.error("Failed to cancel payment", order_id=order_id, error=str(e))
            raise PaymentException(f"Failed to cancel payment: {str(e)}")
    
    async def refund_payment(
        self, order_id: str, amount: Optional[Decimal] = None
    ) -> PaymentRefundResponse:
        """
        Возврат платежа
        
        Args:
            order_id: ID заказа в Сбербанке
            amount: Сумма возврата (если не указана, возвращается полная сумма)
            
        Returns:
            PaymentRefundResponse: Результат возврата платежа
            
        Raises:
            PaymentException: При ошибке возврата платежа
        """
        try:
            payment = await self._get_payment_by_order_id(order_id)
            if not payment:
                raise PaymentException("Payment not found")
            
           # if payment.order_state != PaymentState.PAID:
           #     raise PaymentException("Payment is not in PAID status")
            
            refund_amount_kopecks = int((amount or Decimal(str(payment.order_sum))) * 100)
            
            # Возврат платежа через API Сбербанка
            refund_result = await self.sberbank_service.refund_payment(
                order_id, refund_amount_kopecks
            )
            
            if refund_result.get("errorCode") != "0":
                error_msg = refund_result.get("errorMessage", "Unknown error")
                error_code = refund_result.get("errorCode")
                
                await self._update_payment_by_id(
                    payment.sbp_id,
                    {
                        "order_state": PaymentState.DECLINED,
                        "error_code": error_code,
                        "error_description": error_msg,
                        "operation_date_time": datetime.now()
                    }
                )
                
                logger.error(
                    "Failed to refund payment via Sberbank API",
                    order_id=order_id,
                    error_code=error_code,
                    error_message=error_msg,
                    result=refund_result
                )
                
                #raise PaymentException(f"Failed to refund payment: {error_msg}")
            
            # Обновление статуса в базе
            await self._update_payment_by_id(
                payment.sbp_id,
                {
                    "order_state": PaymentState.REFUNDED,
                    "operation_date_time": datetime.now()
                }
            )
            
            logger.info(
                "Payment refunded successfully",
                order_id=order_id,
                refund_amount=refund_amount_kopecks / 100
            )
            
            return PaymentRefundResponse(
                success=True,
                sbp_id=payment.sbp_id,
                order_id=order_id,
                status=PaymentState.REFUNDED,
                refund_amount=Decimal(refund_amount_kopecks) / 100,
                message="Payment refunded successfully"
            )
            
        except PaymentException:
            raise
        except Exception as e:
            logger.error("Failed to refund payment", order_id=order_id, error=str(e))
            raise PaymentException(f"Failed to refund payment: {str(e)}")
    
    async def process_callback_payment(
        self, order_id: str, order_number: str, operation: str, status: int,
        additional_params: Optional[dict] = None
    ) -> None:
        """
        Обработка callback уведомления о платеже
        
        Args:
            md_order: UUID заказа в Платёжном шлюзе
            order_number: Номер заказа в системе Партнера (sbp_id)
            operation: Тип операции
            status: Статус операции callback (0 - неуспешно, 1 - успешно)
            additional_params: Дополнительные параметры
        """
        try:
            logger.debug(
                "Processing callback payment",
                operation=operation,
                order_id=order_id,
                order_number=order_number,                
                status=status,
                additional_params=additional_params
            )
            
            # Сначала ищем платеж по order_id (mdOrder)
            payment = None
            if order_id:
                payment = await self._get_payment_by_order_id(order_id)
            
            # Если не найден, пробуем найти по sbp_id (orderNumber)
            if not payment:
                try:
                    sbp_id = int(order_number)
                    payment = await self._get_payment_by_id(sbp_id)
                    logger.info(
                        "Payment found by sbp_id callback",
                        sbp_id=sbp_id,
                        order_id=order_id
                    )
                except ValueError:
                    logger.warning(
                        "Invalid orderNumber format",
                        order_number=order_number
                    )
                
                if not payment:
                    logger.warning(
                        "Payment not found for callback",
                        order_id=order_id,
                        order_number=order_number
                    )
                    return
            
            # Проверяем успешность операции callback
            if status != 1:
                logger.warning(
                    "Callback operation failed",
                    order_id=order_id,
                    order_number=order_number,
                    operation=operation,
                    callback_status=status
                )
                
                # Обновляем статус на DECLINED при неуспешном callback
                await self._update_payment_by_id(
                    payment.sbp_id,
                    {
                       # "order_state": PaymentState.DECLINED,
                        "error_description": f"Callback failed with status {status}",
                        "operation_date_time": datetime.now()
                    }
                )
                return
            
            # Определяем новый статус на основе типа операции
            new_status = self._map_operation_to_status(operation)
            
            logger.debug(
                "Mapped payment status from operation callback",
                operation=operation,
                order_id=order_id,
                order_number=order_number,
                sbp_id=payment.sbp_id,
                old_status=payment.order_state,
                new_status=new_status                
            )
            
            # Обновление статуса в базе
            await self._update_payment_by_id(
                payment.sbp_id,
                {
                    "order_state": new_status,
                    "operation_date_time": datetime.now()
                }
            )
            
            # Обработка операции "deposited" (завершение платежа)
            if operation == "deposited" and new_status == PaymentState.PAID:
                logger.info(
                    "Processing PAID status from callback",
                    operation=operation,
                    order_id=order_id,
                    order_number=order_number,
                    sbp_id=payment.sbp_id                    
                )
                
                # Обновляем данные платежа для актуальной информации
                updated_payment = await  self._get_payment_by_order_id(order_id)
                if updated_payment:
                    await self._process_paid_payment(updated_payment)
                else:
                    logger.error(
                        "Failed to get updated payment data callback",
                        sbp_id=payment.sbp_id
                    )
            
            logger.debug(
                "Callback payment processed",
                operation=operation,
                order_id=order_id,
                order_number=order_number,
                sbp_id=payment.sbp_id,
                callback_status=status
            )
            
        except Exception as e:
            logger.error(
                "Failed to process callback payment",
                operation=operation,
                order_id=order_id,
                order_number=order_number,                
                status=status,
                error=str(e),
                exc_info=True
            )
    
    async def _create_payment_log(self, payment_data: dict) -> PaymentLog:
        """
        Создание записи в логе платежей
        
        Args:
            payment_data: Данные платежа
            
        Returns:
            PaymentLog: Созданная запись
        """
        payment = PaymentLog(**payment_data)
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment
    
    async def _get_payment_by_id(self, sbp_id: int) -> Optional[PaymentLog]:
        """
        Поиск платежа по sbp_id
        
        Args:
            sbp_id: ID записи в таблице PAY_SBP_LOG2
            
        Returns:
            Optional[PaymentLog]: Найденный платеж или None
        """
        result = await self.db.execute(
            select(PaymentLog).where(PaymentLog.sbp_id == sbp_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_payment_by_order_id(self, order_id: str) -> Optional[PaymentLog]:
        """
        Поиск заказа по order_id
        
        Args:
            order_id: ID заказа в Сбербанке
            
        Returns:
            Optional[PaymentLog]: Найденный платеж или None
        """
        result = await self.db.execute(
            select(PaymentLog).where(PaymentLog.order_id == order_id)
        )
        return result.scalar_one_or_none()
    
    async def _update_payment_by_id(
        self,
        sbp_id: int,
        update_data: dict
    ) -> None:
        """
        Обновление заказа по ID
        
        Args:
            sbp_id: ID записи в таблице PAY_SBP_LOG2
            update_data: Данные для обновления
        """
        payment = await self._get_payment_by_id(sbp_id)
        if payment:
            for key, value in update_data.items():
                if hasattr(payment, key):
                    setattr(payment, key, value)
            await self.db.commit()
    
    async def _process_paid_payment(self, payment: PaymentLog) -> None:
        """
        Обработка платежа со статусом PAID (orderStatus = 2)
        Вставляет платеж в таблицу FEE с атомарной защитой от дубликатов

        Args:
            payment: Платеж для обработки
        """
        try:
            logger.info(
                "Processing PAID payment",
                order_id=payment.order_id,
                sbp_id=payment.sbp_id,
                amount=payment.order_sum
            )

            fid = await self._insert_to_fee(payment)

            if fid is None:
                logger.warning(
                    "Duplicate payment or failed to insert into FEE table",
                    order_id=payment.order_id,
                    uid=payment.uid
                )
                return
            
            logger.debug(
                "Payment inserted into FEE table",
                order_id=payment.order_id,
                sbp_id=payment.sbp_id,
                fid=fid
            )
            
            # Отправка фискального чека
           # if payment.fiscal_email:
            await self.atol_service.send_fiscal_receipt(
                account=payment.account,
                fid=fid,
                order_id=payment.order_id,
                amount=payment.order_sum,
                email=payment.fiscal_email,
                phone=payment.fiscal_phone
            )
            logger.info("Fiscal receipt sent successfully", order_id=payment.order_id, sbp_id=payment.sbp_id, fid=fid)
                
        except Exception as e:
            logger.error(
                "Failed to process paid payment",
                order_id=payment.order_id,
                sbp_id=payment.sbp_id,
                error=str(e)
            )
    
    async def _insert_to_fee(self, payment: PaymentLog) -> Optional[int]:
        """
        Вставка записи в таблицу FEE с защитой от дубликатов на уровне БД

        Использует уникальный индекс (uid, comment, ticket_id) для атомарной
        защиты от race conditions при одновременных платежах.

        Args:
            payment: Данные платежа

        Returns:
            Optional[int]: ID созданной записи или None если дубль
        """
        date_pay = payment.operation_date_time if payment.operation_date_time else (
            payment.rq_tm if payment.rq_tm else datetime.now()
        )
        sum_paid = Decimal(str(payment.order_sum))
        uid = payment.uid
        comment = payment.order_id

        query = text("""
            INSERT IGNORE INTO FEE (uid, date_pay, sum_paid, method, comment, ticket_id)
            VALUES (:uid, :date_pay, :sum_paid, 5, :comment, 'SBP')
        """)

        result = await self.db.execute(query, {
            "uid": uid,
            "date_pay": date_pay,
            "sum_paid": sum_paid,
            "comment": comment
        })

        await self.db.commit()

        if result.rowcount > 0:
            query_get_id = text("""
                SELECT fid FROM FEE
                WHERE uid = :uid AND comment = :comment AND ticket_id = 'SBP'
                LIMIT 1
            """)
            result_id = await self.db.execute(query_get_id, {
                "uid": uid,
                "comment": comment
            })
            row = result_id.fetchone()
            return row[0] if row else None
        return None
    
    def _generate_rq_uid(self) -> str:
        """
        Генерация уникального идентификатора запроса аналогично PHP коду:
        str_pad(md5(date('c')), 32, (string)rand())
        
        Returns:
            str: Уникальный идентификатор
        """
        # Получаем текущую дату в формате ISO 8601 (аналог date('c') в PHP)
        current_date = datetime.now().isoformat()
        
        # Создаем MD5 хеш от даты
        md5_hash = hashlib.md5(current_date.encode()).hexdigest()
        
        # Дополняем до 32 символов случайными цифрами (аналог str_pad с rand())
        while len(md5_hash) < 32:
            md5_hash += str(random.randint(0, 9))
        
        return md5_hash[:32]
    
    def _map_sberbank_status(self, status: int) -> PaymentState:
        """
        Маппинг статуса Сбербанка в внутренний статус
        
        Args:
            status: Числовой статус от Сбербанка
            
        Returns:
            PaymentState: Внутренний статус
        """
        status_map = {
            0: PaymentState.CREATED,      # заказ зарегистрирован, но не оплачен
            1: PaymentState.AUTHORIZED,   # сумма захолдирована (для двухстадийного сценария)
            2: PaymentState.PAID,         # проведена полная авторизация суммы заказа
            3: PaymentState.DECLINED,     # авторизация отменена
            4: PaymentState.REFUNDED,     # по заказу была проведена операция возврата
            5: PaymentState.ON_PAYMENT,   # инициирована аутентификация через ACS Банка-эмитента
            6: PaymentState.DECLINED      # авторизация отклонена
        }
        return status_map.get(status, PaymentState.CREATED)
    
    def _map_operation_to_status(self, operation: str) -> PaymentState:
        """
        Маппинг типа операции в внутренний статус
        
        Args:
            operation: Тип операции от Сбербанка
            
        Returns:
            PaymentState: Внутренний статус
        """
        operation_map = {
            "created": PaymentState.CREATED,           # заказ создан
            "approved": PaymentState.AUTHORIZED,       # операция удержания (холдирования)
            "deposited": PaymentState.PAID,            # операция завершения
            "reversed": PaymentState.DECLINED,         # операция отмены
            "refunded": PaymentState.REFUNDED,         # операция возврата
            "declinedByTimeout": PaymentState.EXPIRED, # истекло время на оплату
            "subscriptionCreated": PaymentState.PAID   # подписка создана
        }
        return operation_map.get(operation, PaymentState.CREATED)
    
    
    async def _get_customer_uid(self, account: str) -> Optional[int]:
        """
        Проверка наличия пользователя в биллинге
        
        Args:
            pin: Договор           
            
        Returns:
            Optional[int]: uid существующей записи или None если её нет
        """
        query = text("""
            SELECT uid FROM CUSTOMER 
            WHERE pin = :account
            LIMIT 1
        """)
        
        result = await self.db.execute(query, {            
            "account": account
        })
        
        row = result.fetchone()
        return row[0] if row else None
