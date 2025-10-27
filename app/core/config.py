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
    
    # Сбербанк API
    SBERBANK_API_URL: str = Field(
        default="https://ecomift.sberbank.ru/ecomm/gw/partner/api/v1",
        description="URL API Сбербанка"
    )
    SBERBANK_API_URL_PROD: str = Field(
        default="https://epay.sberbank.ru/ecomm/gw/partner/api/v1",
        description="URL продакшн API Сбербанка"
    )
    SBERBANK_USERNAME: str = Field(..., description="Логин Сбербанк API")
    SBERBANK_PASSWORD: str = Field(..., description="Пароль Сбербанк API")
    SBERBANK_RETURN_URL: str = Field(default="https://stat.starlink.ru/payment/", description="URL для получения статуса от банка")
    
    # АТОЛ фискализация
    ATOL_PAYMENT_ID: str = Field(default="SBP", description="ATOL_PAYMENT_ID")
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
        return self.SBERBANK_API_URL_PROD if not self.DEBUG else self.SBERBANK_API_URL


@lru_cache()
def get_settings() -> Settings:
    """
    Получение настроек приложения (кэшированное)
    
    Returns:
        Settings: Экземпляр настроек
    """
    return Settings()