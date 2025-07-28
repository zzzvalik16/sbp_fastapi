"""
Сервис для работы с платежами
"""

import uuid
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
            #rq_uid = self._generate_rq_uid()
            payment_data = {
                "uid": request.uid,                
                "order_sum": float(request.amount),                
                "account": request.account,
                "fiscal_email": str(request.email)
            }
            if request.phone:
                payment_data["fiscal_phone"] = request.phone
            orderNumber = await self._create_payment_log(payment_data)
            
            # Создание QR кода через API Сбербанка
            sberbank_response = await self.sberbank_service.create_qr_code(
                order_number=orderNumber,
                amount=int(request.amount * 100),  # Конвертация в копейки
                description=f"Пополнение лицевого счета №{request.account}",
                email=str(request.email)
            )
            
            # Извлечение sbpPayload из ответа
            sbp_payload = sberbank_response.get("externalParams", {}).get("sbpPayload")
            qrcId = sberbank_response.get("externalParams", {}).get("qrcId")
            if not sbp_payload:
                raise PaymentException("SBP payload not received from Sberbank")
            
            # Сохранение платежа в базе данных
            payment_data = {
                "rq_uid": qrcId,
                "order_state": PaymentState.CREATED,
                "order_form_url": sbp_payload,
                "source_payments": request.payment_stat               
            }
            
            # Добавление опциональных полей
            if request.uid:
                payment_data["uid"] = request.uid
            if sberbank_response.get("orderId"):
                payment_data["order_id"] = sberbank_response["orderId"]
           
            
            await self._create_payment_log(payment_data)
            
            logger.info(
                "Payment created successfully",
                rq_uid=qrcId,
                order_id=sberbank_response.get("orderId"),
                amount=request.amount
            )
            
            return PaymentCreateResponse(
                success=True,
                rq_uid=qrcId,
                order_id=sberbank_response.get("orderId"),
                qr_payload=sbp_payload,
                qr_url=sberbank_response.get("formUrl"),
                amount=request.amount,
                status=PaymentState.CREATED
            )
            
        except Exception as e:
            logger.error("Failed to create payment", error=str(e))
            raise PaymentException(f"Failed to create payment: {str(e)}")
    
    async def get_payment_status(self, rq_uid: str) -> PaymentStatusResponse:
        """
        Получение статуса платежа
        
        Args:
            rq_uid: Уникальный идентификатор запроса
            
        Returns:
            PaymentStatusResponse: Статус платежа
            
        Raises:
            PaymentException: При ошибке получения статуса
        """
        try:
            # Поиск платежа в базе данных
            payment = await self._get_payment_by_rq_uid(rq_uid)
            if not payment:
                raise PaymentException("Payment not found")
            
            # Получение актуального статуса из API Сбербанка
            if payment.order_id:
                try:
                    sberbank_status = await self.sberbank_service.get_payment_status(
                        payment.order_id
                    )
                    
                    if sberbank_status.get("errorCode") == "0":
                        new_status = self._map_sberbank_status(
                            sberbank_status.get("orderStatus", 0)
                        )
                        
                        # Обновление статуса в базе, если он изменился
                        if payment.order_state != new_status:
                            await self._update_payment_status(
                                rq_uid, new_status,
                                operation_date_time=sberbank_status.get("depositedDate")
                            )
                            payment.order_state = new_status
                            
                            # Обработка статуса PAID (orderStatus = 2)
                            if new_status == PaymentState.PAID:
                                await self._process_paid_payment(payment)
                                
                except Exception as e:
                    logger.warning(
                        "Failed to get status from Sberbank API",
                        rq_uid=rq_uid,
                        error=str(e)
                    )
            
            return PaymentStatusResponse(
                success=True,
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
            logger.error("Failed to get payment status", rq_uid=rq_uid, error=str(e))
            raise PaymentException(f"Failed to get payment status: {str(e)}")
    
    async def cancel_payment(self, rq_uid: str) -> PaymentCancelResponse:
        """
        Отмена платежа
        
        Args:
            rq_uid: Уникальный идентификатор запроса
            
        Returns:
            PaymentCancelResponse: Результат отмены платежа
            
        Raises:
            PaymentException: При ошибке отмены платежа
        """
        try:
            payment = await self._get_payment_by_rq_uid(rq_uid)
            if not payment:
                raise PaymentException("Payment not found")
            
            if not payment.order_id:
                raise PaymentException("Order ID not found")
            
            # Отмена платежа через API Сбербанка
            cancel_result = await self.sberbank_service.cancel_payment(payment.order_id)
            
            if cancel_result.get("errorCode") != "0":
                error_msg = cancel_result.get("errorMessage", "Unknown error")
                await self._update_payment_status(
                    rq_uid, PaymentState.DECLINED,
                    error_code=cancel_result.get("errorCode"),
                    error_description=error_msg
                )
                raise PaymentException(f"Failed to cancel payment: {error_msg}")
            
            # Обновление статуса в базе
            await self._update_payment_status(rq_uid, PaymentState.DECLINED)
            
            logger.info("Payment cancelled successfully", rq_uid=rq_uid)
            
            return PaymentCancelResponse(
                success=True,
                rq_uid=rq_uid,
                status=PaymentState.DECLINED,
                message="Payment cancelled successfully"
            )
            
        except PaymentException:
            raise
        except Exception as e:
            logger.error("Failed to cancel payment", rq_uid=rq_uid, error=str(e))
            raise PaymentException(f"Failed to cancel payment: {str(e)}")
    
    async def refund_payment(
        self, rq_uid: str, amount: Optional[Decimal] = None
    ) -> PaymentRefundResponse:
        """
        Возврат платежа
        
        Args:
            rq_uid: Уникальный идентификатор запроса
            amount: Сумма возврата (если не указана, возвращается полная сумма)
            
        Returns:
            PaymentRefundResponse: Результат возврата платежа
            
        Raises:
            PaymentException: При ошибке возврата платежа
        """
        try:
            payment = await self._get_payment_by_rq_uid(rq_uid)
            if not payment:
                raise PaymentException("Payment not found")
            
            if not payment.order_id:
                raise PaymentException("Order ID not found")
            
            if payment.order_state != PaymentState.PAID:
                raise PaymentException("Payment is not in PAID status")
            
            refund_amount_kopecks = int((amount or Decimal(str(payment.order_sum))) * 100)
            
            # Возврат платежа через API Сбербанка
            refund_result = await self.sberbank_service.refund_payment(
                payment.order_id, refund_amount_kopecks
            )
            
            if refund_result.get("errorCode") != "0":
                error_msg = refund_result.get("errorMessage", "Unknown error")
                await self._update_payment_status(
                    rq_uid, PaymentState.DECLINED,
                    error_code=refund_result.get("errorCode"),
                    error_description=error_msg
                )
                raise PaymentException(f"Failed to refund payment: {error_msg}")
            
            # Обновление статуса в базе
            await self._update_payment_status(rq_uid, PaymentState.REFUNDED)
            
            logger.info(
                "Payment refunded successfully",
                rq_uid=rq_uid,
                refund_amount=refund_amount_kopecks / 100
            )
            
            return PaymentRefundResponse(
                success=True,
                rq_uid=rq_uid,
                status=PaymentState.REFUNDED,
                refund_amount=Decimal(refund_amount_kopecks) / 100,
                message="Payment refunded successfully"
            )
            
        except PaymentException:
            raise
        except Exception as e:
            logger.error("Failed to refund payment", rq_uid=rq_uid, error=str(e))
            raise PaymentException(f"Failed to refund payment: {str(e)}")
    
    async def process_webhook_payment(
        self, order_id: str, status: int, order_status: Optional[int] = None,
        additional_params: Optional[dict] = None
    ) -> None:
        """
        Обработка webhook уведомления о платеже
        
        Args:
            md_order: UUID заказа в Платёжном шлюзе
            order_number: Номер заказа в системе Партнера
            operation: Тип операции
            status: Статус операции callback (0 - неуспешно, 1 - успешно)
            additional_params: Дополнительные параметры
        """
        try:
            logger.info(
                "Processing webhook payment",
                md_order=md_order,
                order_number=order_number,
                operation=operation,
                status=status,
                additional_params=additional_params
            )
            
            # Ищем платеж по order_id (mdOrder) или по rq_uid (orderNumber)
            payment = await self._get_payment_by_order_id(md_order)
            if not payment:
                # Пробуем найти по orderNumber (rq_uid)
                payment = await self._get_payment_by_rq_uid(order_number)
                if not payment:
                    logger.warning(
                        "Payment not found for webhook",
                        md_order=md_order,
                        order_number=order_number
                    )
                    return
            
            # Проверяем успешность операции callback
            if status != 1:
                logger.warning(
                    "Callback operation failed",
                    md_order=md_order,
                    order_number=order_number,
                    operation=operation,
                    callback_status=status
                )
                
                # Обновляем статус на DECLINED при неуспешном callback
                await self._update_payment_status(
                    payment.rq_uid,
                    PaymentState.DECLINED,
                    error_description=f"Callback failed with status {status}"
                )
                return
            
            # Определяем новый статус на основе типа операции
            new_status = self._map_operation_to_status(operation)
            
            logger.info(
                "Mapped payment status from operation",
                md_order=md_order,
                order_number=order_number,
                rq_uid=payment.rq_uid,
                old_status=payment.order_state,
                new_status=new_status,
                operation=operation
            )
            
            # Обновление статуса в базе
            await self._update_payment_status(
                payment.rq_uid,
                new_status
            )
            
            # Обработка операции "deposited" (завершение платежа)
            if operation == "deposited" and new_status == PaymentState.PAID:
                logger.warning(
                    "Processing PAID status from webhook",
                    md_order=md_order,
                    order_number=order_number,
                    rq_uid=payment.rq_uid,
                    operation=operation
                )
                
                # Обновляем данные платежа для актуальной информации
                updated_payment = await self._get_payment_by_rq_uid(payment.rq_uid)
                if updated_payment:
                    await self._process_paid_payment(updated_payment)
                else:
                    logger.error(
                        "Failed to get updated payment data",
                        rq_uid=payment.rq_uid
                    )
            else:
                logger.info(
                    "Payment status updated, no additional processing needed",
                    md_order=md_order,
                    order_number=order_number,
                    rq_uid=payment.rq_uid,
                    status=new_status,
                    operation=operation
                )
            
            logger.info(
                "Webhook payment processed",
                md_order=md_order,
                order_number=order_number,
                rq_uid=payment.rq_uid,
                callback_status=status,
                operation=operation
            )
            
        except Exception as e:
            logger.error(
                "Failed to process webhook payment",
                md_order=md_order,
                order_number=order_number,
                operation=operation,
                status=status,
                error=str(e)
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
    
    async def _get_payment_by_rq_uid(self, rq_uid: str) -> Optional[PaymentLog]:
        """
        Поиск платежа по rq_uid
        
        Args:
            rq_uid: Уникальный идентификатор запроса
            
        Returns:
            Optional[PaymentLog]: Найденный платеж или None
        """
        result = await self.db.execute(
            select(PaymentLog).where(PaymentLog.rq_uid == rq_uid)
        )
        return result.scalar_one_or_none()
    
    async def _get_payment_by_order_id(self, order_id: str) -> Optional[PaymentLog]:
        """
        Поиск платежа по order_id
        
        Args:
            order_id: ID заказа в Сбербанке
            
        Returns:
            Optional[PaymentLog]: Найденный платеж или None
        """
        result = await self.db.execute(
            select(PaymentLog).where(PaymentLog.order_id == order_id)
        )
        return result.scalar_one_or_none()
    
    async def _update_payment_status(
        self,
        rq_uid: str,
        status: PaymentState,
        error_code: Optional[str] = None,
        error_description: Optional[str] = None,
        operation_date_time: Optional[int] = None
    ) -> None:
        """
        Обновление статуса платежа
        
        Args:
            rq_uid: Уникальный идентификатор запроса
            status: Новый статус
            error_code: Код ошибки
            error_description: Описание ошибки
            operation_date_time: Время операции (timestamp в миллисекундах)
        """
        payment = await self._get_payment_by_rq_uid(rq_uid)
        if payment:
            payment.order_state = status
            
            # Установка времени операции
            if operation_date_time:
                # Конвертация timestamp из миллисекунд в datetime
                payment.operation_date_time = datetime.fromtimestamp(operation_date_time / 1000)
            else:
                payment.operation_date_time = datetime.now()
                
            if error_code:
                payment.error_code = error_code
            if error_description:
                payment.error_description = error_description
            await self.db.commit()
    
    async def _process_paid_payment(self, payment: PaymentLog) -> None:
        """
        Обработка платежа со статусом PAID (orderStatus = 2)
        Проверяет наличие платежа в БД и если его нет - начисляет и отправляет на фискализацию
        
        Args:
            payment: Платеж для обработки
        """
        try:
            logger.info(
                "Processing PAID payment",
                rq_uid=payment.rq_uid,
                order_id=payment.order_id,
                amount=payment.order_sum
            )
            
            # Проверка на дубли платежа в таблице FEE
            existing_fee = await self._check_fee_duplicate(payment.order_id, payment.uid)
            if existing_fee:
                logger.warning(
                    "Duplicate payment found in FEE table, skipping fiscal receipt",
                    order_id=payment.order_id,
                    uid=payment.uid,
                    existing_fid=existing_fee
                )
                return
            
            # Сохранение в таблицу FEE
            fid = await self._insert_to_fee(payment)
            
            if fid is None:
                logger.warning(
                    "Failed to insert into FEE table, skipping fiscal receipt",
                    order_id=payment.order_id,
                    uid=payment.uid
                )
                return
            
            logger.info(
                "Payment inserted into FEE table",
                rq_uid=payment.rq_uid,
                fid=fid
            )
            
            # Отправка фискального чека
            if payment.fiscal_email:
                await self.atol_service.send_fiscal_receipt(
                    account=payment.account,
                    fid=fid,
                    rq_uid=payment.rq_uid,
                    amount=payment.order_sum,
                    email=payment.fiscal_email,
                    phone=payment.fiscal_phone
                )
                logger.info("Fiscal receipt sent successfully", rq_uid=payment.rq_uid, fid=fid)
                
        except Exception as e:
            logger.error(
                "Failed to process paid payment",
                rq_uid=payment.rq_uid,
                error=str(e)
            )
    
    async def _check_fee_duplicate(self, order_id: str, uid: int) -> Optional[int]:
        """
        Проверка наличия дубля платежа в таблице FEE
        
        Args:
            order_id: ID заказа в Сбербанке
            uid: ID пользователя
            
        Returns:
            Optional[int]: fid существующей записи или None если дубля нет
        """
        query = text("""
            SELECT fid FROM FEE 
            WHERE comment = :order_id AND uid = :uid AND ticket_id = 'SBP'
            LIMIT 1
        """)
        
        result = await self.db.execute(query, {
            "order_id": order_id,
            "uid": uid
        })
        
        row = result.fetchone()
        return row[0] if row else None
    
    async def _insert_to_fee(self, payment: PaymentLog) -> Optional[int]:
        """
        Вставка записи в таблицу FEE с проверкой на дубли
        
        Args:
            payment: Данные платежа
            
        Returns:
            Optional[int]: ID созданной записи или None если дубль
        """
        # Определение даты платежа согласно логике из требований
        date_pay = payment.operation_date_time if payment.operation_date_time else (
            payment.rq_tm if payment.rq_tm else datetime.now()
        )
        sum_paid = Decimal(str(payment.order_sum))
        uid = payment.uid
        comment = payment.order_id
        
        # Запрос с проверкой на дубли
        query = text("""
            INSERT INTO FEE (uid, date_pay, sum_paid, method, comment, ticket_id)
            SELECT :uid, :date_pay, :sum_paid, 5, :comment, 'SBP'
            FROM DUAL
            WHERE NOT EXISTS (
                SELECT comment FROM FEE 
                WHERE comment = :comment_check AND uid = :uid_check AND ticket_id = 'SBP'
            ) LIMIT 1
        """)
        
        result = await self.db.execute(query, {
            "uid": uid,
            "date_pay": date_pay,
            "sum_paid": sum_paid,
            "comment": comment,
            "comment_check": comment,
            "uid_check": uid
        })
        
        await self.db.commit()
        
        if result.rowcount > 0:
            return result.lastrowid
        return None
    
    def _generate_rq_uid(self) -> str:
        """
        Генерация уникального идентификатора запроса
        
        Returns:
            str: Уникальный идентификатор
        """
        return f"RQ_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
    
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