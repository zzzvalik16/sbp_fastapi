"""
Pydantic схемы для работы с платежами
"""

from decimal import Decimal
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr, field_validator

from app.models.payment import PaymentState


class PaymentCreateRequest(BaseModel):
    """
    Схема запроса на создание платежа
    """
    
    amount: Decimal = Field(
        ...,
        gt=0,
        le=999999999999,
        description="Сумма платежа в рублях"
    )
    email: EmailStr = Field(
        ...,
        description="Email плательщика"
    )
    account: str = Field(
        ...,
        min_length=1,
        max_length=6,
        description="Номер лицевого счета"
    )
    paymentStat: str = Field(
        default="sbpStat",
        max_length=10,
        description="Источник платежа"
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=12,
        description="Телефон плательщика"
    )
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Валидация суммы платежа"""
        if v <= 0:
            raise ValueError('Сумма должна быть больше 0')
        return v
    
    @field_validator('account')
    @classmethod
    def validate_account(cls, v):
        """Валидация номера счета"""
        if not v.isdigit():
            raise ValueError('Номер счета должен содержать только цифры')
        return v


class PaymentCreateResponse(BaseModel):
    """
    Схема ответа на создание платежа
    """
    
    success: bool = Field(..., description="Статус успешности операции")
    sbp_id: int = Field(..., description="ID записи в таблице PAY_SBP_LOG2")
    rq_uid: str = Field(..., description="Уникальный идентификатор запроса")
    order_id: Optional[str] = Field(default=None, description="ID заказа в Сбербанке")
    qrcode_link: str = Field(..., description="Платежная ссылка для QR кода")
    qr_url: Optional[str] = Field(default=None, description="URL формы оплаты")
    amount: Decimal = Field(..., description="Сумма платежа")
    status: PaymentState = Field(..., description="Статус платежа")


class PaymentStatusResponse(BaseModel):
    """
    Схема ответа на запрос статуса платежа
    """
    
    success: bool = Field(..., description="Статус успешности операции")
    sbp_id: int = Field(..., description="ID записи в таблице PAY_SBP_LOG2")
    rq_uid: str = Field(..., description="Уникальный идентификатор запроса")
    order_id: Optional[str] = Field(default=None, description="ID заказа в Сбербанке")
    status: PaymentState = Field(..., description="Статус платежа")
    amount: Optional[Decimal] = Field(default=None, description="Сумма платежа")
    account: Optional[str] = Field(default=None, description="Номер лицевого счета")
    created_at: Optional[datetime] = Field(default=None, description="Дата создания")
    operation_time: Optional[datetime] = Field(default=None, description="Время операции")


class PaymentCancelResponse(BaseModel):
    """
    Схема ответа на отмену платежа
    """
    
    success: bool = Field(..., description="Статус успешности операции")
    sbp_id: int = Field(..., description="ID записи в таблице PAY_SBP_LOG2")
    order_id: str = Field(..., description="ID заказа в Сбербанке")
    status: PaymentState = Field(..., description="Новый статус платежа")
    message: str = Field(..., description="Сообщение об операции")


class PaymentRefundRequest(BaseModel):
    """
    Схема запроса на возврат платежа
    """
    
    amount: Optional[Decimal] = Field(
        default=None,
        gt=0,
        description="Сумма возврата (если не указана, возвращается полная сумма)"
    )


class PaymentRefundResponse(BaseModel):
    """
    Схема ответа на возврат платежа
    """
    
    success: bool = Field(..., description="Статус успешности операции")
    sbp_id: int = Field(..., description="ID записи в таблице PAY_SBP_LOG2")
    order_id: str = Field(..., description="ID заказа в Сбербанке")
    status: PaymentState = Field(..., description="Новый статус платежа")
    refund_amount: Decimal = Field(..., description="Сумма возврата")
    message: str = Field(..., description="Сообщение об операции")


class CallbackPaymentData(BaseModel):
    """
    Схема данных callback уведомления о платеже от Сбербанка

    Обязательные поля:
    - mdOrder: Номер заказа в платежном шлюзе
    - orderNumber: Номер заказа в системе партнера
    - operation: Тип операции (например: deposited, approved, reversed)
    - status: Статус операции (0-10)

    Необязательные поля:
    - checksum: Контрольная сумма для проверки подлинности
    - additionalParams: Дополнительные параметры от платежной системы
    """

    mdOrder: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Уникальный номер заказа в Платежном шлюзе (обязательно)"
    )
    orderNumber: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Уникальный номер заказа в системе Партнера (обязательно)"
    )
    operation: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Тип операции (обязательно)"
    )
    status: int = Field(
        ...,
        ge=0,
        le=10,
        description="Статус операции callback: 0-неуспешно, 1-успешно (обязательно)"
    )
    checksum: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Контрольная сумма для проверки подлинности (необязательно)"
    )
    additionalParams: Optional[dict] = Field(
        default=None,
        description="Дополнительные параметры от платежной системы (необязательно)"
    )