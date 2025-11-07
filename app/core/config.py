"""
Конфигурация приложения
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Настройки приложения с валидацией через Pydantic
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra='ignore'
    )
    
    # Приложение
    DEBUG: bool = Field(default=True, description="Режим отладки")
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")
    ALLOWED_ORIGINS: List[str] = Field(default=["*"], description="Разрешенные CORS origins")
    
    # База данных
    DB_HOST: str = Field(..., description="Хост базы данных")
    DB_PORT: int = Field(default=3306, description="Порт базы данных")
    DB_USER: str = Field(..., description="Пользователь базы данных")
    DB_PASSWORD: str = Field(..., description="Пароль базы данных")
    DB_NAME: str = Field(..., description="Имя базы данных")

    REDIS_HOST: str = Field(..., description="Хост базы данных редис")
    REDIS_PORT: int = Field(default=6379, description="Порт базы данных редис")
    REDIS_DB: str = Field(..., description="БД редис")
    REDIS_LOCK_TTL: int = Field(..., description="В секундах")
    
    # Сбербанк API    
    TEST_MODE: bool = Field(default=True, description="Режим работы тестовый иди продакшн")
    SBERBANK_TEST_URL: str = Field(
        default="https://ecomift.sberbank.ru/ecomm/gw/partner/api/v1",
        description="Тестовый URL API СБП Сбербанка"
    )
    SBERBANK_PROD_URL: str = Field(
        default="https://epay.sberbank.ru/ecomm/gw/partner/api/v1",
        description="Продакшн URL API СБП Сбербанка"
    )
    SBERBANK_USERNAME: str = Field(..., description="Логин Сбербанк API")
    SBERBANK_PASSWORD: str = Field(..., description="Пароль Сбербанк API")
    SBERBANK_RETURN_URL: str = Field(default="https://www.starlink.ru/payment/", description="Страница после успешной оплаты")
    SBERBANK_FAIL_RETURN_URL: str = Field(default="https://www.starlink.ru/payment/", description="Страница после неуспешной оплаты")
    SBERBANK_QR_TIMEOUT: int = Field(12, description="Время жизни QR кода в минутах")
    
    # АТОЛ фискализация
    ATOL_PAYMENT_ID: str = Field(default="SBP2", description="ATOL_PAYMENT_ID")
    ATOL_LOGIN: str = Field(..., description="Логин АТОЛ")
    ATOL_PASSWORD: str = Field(..., description="Пароль АТОЛ")
    ATOL_URL: str = Field(
        default="https://atol.starlink.ru/api/v1/atol/register",
        description="URL АТОЛ API"
    )
    
    # Callback
    CALLBACK_SECRET: str = Field(default="", description="Секрет для callback")
    
    @property
    def database_url(self) -> str:
        """
        Формирование URL подключения к базе данных
        
        Returns:
            str: URL подключения к MySQL
        """
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    @property
    def sberbank_api_url(self) -> str:
        """
        Получение URL API Сбербанка в зависимости от режима
        
        Returns:
            str: URL API Сбербанка
        """
        return self.SBERBANK_PROD_URL if not self.TEST_MODE else self.SBERBANK_TEST_URL


@lru_cache()
def get_settings() -> Settings:
    """
    Получение настроек приложения (кэшированное)
    
    Returns:
        Settings: Экземпляр настроек
    """
    return Settings()