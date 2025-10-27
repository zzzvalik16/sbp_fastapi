"""
Модели для работы с платежами
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    CHAR, DECIMAL, VARCHAR, Column, DateTime, Enum as SQLEnum, 
    Float, Index, Integer, String, TIMESTAMP, text
)
from sqlalchemy.sql import func

from app.core.database import Base


class PaymentState(str, Enum):
    """Статусы платежей"""
    PAID = "PAID"
    CREATED = "CREATED"
    REVERSED = "REVERSED"
    REFUNDED = "REFUNDED"
    REVOKED = "REVOKED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    AUTHORIZED = "AUTHORIZED"
    CONFIRMED = "CONFIRMED"
    ON_PAYMENT = "ON_PAYMENT"


class PaymentLog(Base):
    """
    Модель для таблицы PAY_SBP_LOG2
    Логирование всех операций с платежами СБП
    """
    
    __tablename__ = "PAY_SBP_LOG2"
    
    sbp_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Уникальный идентификатор записи"
    )
    uid = Column(
        Integer,
        nullable=False,
        comment="Идентификатор пользователя"
    )
    account = Column(
        VARCHAR(6),
        nullable=False,
        default="",
        comment="Номер лицевого счета"
    )
    rq_uid = Column(
        VARCHAR(32),
        nullable=True,
        comment="Уникальный идентификатор запроса"
    )
    order_sum = Column(
        Float(12),
        nullable=True,
        comment="Сумма заказа в минимальных единицах валюты"
    )
    order_create_date = Column(
        TIMESTAMP,
        nullable=True,
        server_default=func.current_timestamp(),
        comment="Дата/время формирования заказа"
    )
    order_id = Column(
        VARCHAR(36),
        nullable=True,
        comment="ID заказа в АС ППРБ.Карты"
    )
    order_state = Column(
        SQLEnum(PaymentState),
        nullable=True,
        comment="Статус заказа"
    )
    order_form_url = Column(
        VARCHAR(256),
        nullable=True,
        comment="Ссылка на считывание QR code"
    )
    rq_tm = Column(
        TIMESTAMP,
        nullable=True,
        comment="Дата/время формирования запроса"
    )
    operation_date_time = Column(
        "operationDateTime",
        TIMESTAMP,
        nullable=True,
        comment="Дата/время операции"
    )
    error_code = Column(
        CHAR(6),
        nullable=True,
        comment="Код выполнения запроса"
    )
    error_description = Column(
        VARCHAR(256),
        nullable=True,
        comment="Описание ошибки выполнения запроса"
    )
    source_payments = Column(
        VARCHAR(10),
        nullable=True,
        default="sbpStat",
        comment="Источник платежа"
    )
    fiscal_email = Column(
        VARCHAR(100),
        nullable=True,
        comment="Email для фискализации"
    )
    fiscal_phone = Column(
        VARCHAR(12),
        nullable=True,
        comment="Телефон для фискализации"
    )
    
    # Индексы
    __table_args__ = (
        Index("trans_id", "rq_uid"),
    )


class Fee(Base):
    """
    Модель для таблицы FEE
    Учет платежей для фискализации
    """
    
    __tablename__ = "FEE"
    
    fid = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Уникальный идентификатор записи"
    )
    uid = Column(
        Integer,
        nullable=False,
        comment="Идентификатор пользователя"
    )
    date_pay = Column(
        DateTime,
        nullable=False,
        comment="Дата платежа"
    )
    sum_paid = Column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Сумма платежа"
    )
    method = Column(
        Integer,
        nullable=False,
        comment="Метод платежа"
    )
    comment = Column(
        VARCHAR(255),
        nullable=True,
        comment="Комментарий к платежу"
    )
    ticket_id = Column(
        VARCHAR(20),
        nullable=False,
        comment="Идентификатор тикета"
    )
    
    # Индексы
    __table_args__ = (
        Index("XPKFEE", "uid", "fid", unique=True),
        Index("fee_uid", "uid"),
        Index("date_pay", "date_pay"),
        Index("ticket_id", "ticket_id"),
        Index("comment", "comment"),
        Index("method", "method"),
    )