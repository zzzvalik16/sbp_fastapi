# FastAPI СБП API

Современный API для работы с Системой Быстрых Платежей (СБП) через Сбербанк, построенный на FastAPI с автоматической фискализацией через АТОЛ.

## Технические характеристики

- **Python**: 3.12
- **FastAPI**: Последняя версия с полной поддержкой async/await
- **SQLAlchemy**: 2.0+ с асинхронной поддержкой
- **База данных**: MySQL 5.7
- **Валидация**: Pydantic v2 с полной типизацией
- **Логирование**: Структурированное логирование через structlog
- **Контейнеризация**: Docker + docker-compose

## Архитектура проекта

```
app/
├── main.py                 # Главный модуль приложения
├── core/                   # Основные компоненты
│   ├── config.py          # Конфигурация через Pydantic Settings
│   ├── database.py        # Настройка SQLAlchemy
│   ├── exceptions.py      # Обработка исключений
│   └── logging.py         # Настройка логирования (с ежедневной ротацией)
├── models/                 # SQLAlchemy модели
│   └── payment.py         # Модели платежей и callback логов
├── schemas/                # Pydantic схемы
│   └── payment.py         # Схемы валидации
├── services/               # Бизнес-логика
│   ├── payment_service.py # Сервис платежей
│   ├── sberbank_service.py# Интеграция с Сбербанком
│   └── atol_service.py    # Фискализация АТОЛ
└── api/                   # API endpoints
    ├── dependencies.py    # Dependency Injection
    ├── v1/               # API версия 1
    │   ├── router.py     # Роутер v1
    │   └── endpoints/    # Endpoints v1
    └── v2/               # API версия 2 (будущее)

docker/                     # Docker конфигурация
├── docker-compose.yml     # Docker Compose файл
└── Dockerfile             # Docker образ

.env                        # Переменные окружения (игнорируется Git)
```

## Возможности

### ✅ Полная интеграция с API Сбербанка
- Создание динамических QR-кодов СБП
- Получение статуса платежей в реальном времени
- Отмена и возврат платежей
- Обработка webhook уведомлений

### ✅ Автоматическая фискализация
- Интеграция с АТОЛ для отправки фискальных чеков
- Проверка дублей платежей
- Автоматическая отправка чеков при статусе PAID

### ✅ Современная архитектура
- Принципы ООП и SOLID
- Dependency Injection через FastAPI
- Полная типизация с подсказками
- Асинхронная обработка запросов

### ✅ Надежность и мониторинг
- Структурированное логирование
- Обработка всех типов исключений
- Валидация данных через Pydantic
- Версионирование API (v1, v2)

## Быстрый старт

### 1. Установка через Docker (рекомендуется)

```bash
# Клонирование репозитория
git clone <repository-url>
cd fastapi-sbp-api

# Быстрая установка
make install
```

### 2. Локальная установка (без Docker)

```bash
# Клонирование репозитория
git clone <repository-url>
cd fastapi-sbp-api

# Создание виртуального окружения
python -m venv venv

# Активация виртуального окружения
# На Windows:
venv\Scripts\activate
# На Linux/macOS:
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл с вашими настройками

# Установка и настройка MySQL
# Создайте базу данных sbp_api
# Создайте пользователя sbp_user с паролем sbp_password

# Запуск приложения
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Настройка окружения

Скопируйте `.env.example` в `.env` и настройте переменные:

```bash
cp .env.example .env
```

Основные настройки:
```env
# База данных
DB_HOST=mysql
DB_USER=sbp_user
DB_PASSWORD=sbp_password
DB_NAME=sbp_api

# Сбербанк API
SBERBANK_USERNAME=your_username
SBERBANK_PASSWORD=your_password

# АТОЛ фискализация
ATOL_LOGIN=your_atol_login
ATOL_PASSWORD=your_atol_password
```

### 4. Запуск сервисов (Docker)

```bash
# Запуск всех сервисов
make up

# Просмотр логов
make logs

# Остановка сервисов
make down
```

### 5. Запуск для разработки (локально)

```bash
# Запуск в режиме разработки с автоперезагрузкой
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Или через make команду
make dev
```

## Доступные сервисы

После запуска доступны:
- **API**: http://localhost:8000
- **Документация**: http://localhost:8000/docs (только в режиме разработки, DEBUG=true)
- **ReDoc**: http://localhost:8000/redoc (только в режиме разработки, DEBUG=true)
- **phpMyAdmin**: http://localhost:8080 (только при запуске через Docker)
- **MySQL**: localhost:3306

**Примечание**: В продакшене (DEBUG=false) документация /docs и /redoc автоматически отключаются для безопасности.

## Требования к системе

### Для Docker установки:
- Docker 20.10+
- Docker Compose 2.0+
- 2GB свободной оперативной памяти

### Для локальной установки:
- Python 3.12+
- MySQL 5.7+ или 8.0+
- 1GB свободной оперативной памяти

## API Endpoints

### Создание платежа

```http
POST /api/v1/create
Content-Type: application/json

{
    "amount": "500.00",
    "email": "user@example.com",
    "account": "054350",
    "paymentStat": "sbpStat",    
    "phone": "+79001234567"
}
```

**Ответ:**
```json
{
    "success": true,
    "rq_uid": "RQ_1640995200_abc12345",
    "order_id": "a67b0ced-c9a4-4cfb-bce3-b9595afaafc1",
    "qrcode_link": "https://qr.nspk.ru/AD10006MNS72CPM49QGO1NIUBH13VD8H?type=02&bank=100000000111&sum=50000&cur=RUB&crc=6CB3",
    "qr_url": "https://ecomtest.sberbank.ru/pp/pay_ru?orderId=...",
    "amount": "500.00",
    "status": "CREATED"
}
```

### Получение статуса платежа

```http
GET /api/v1/status/{rq_uid}
```

### Отмена платежа

```http
POST /api/v1/cancel/{rq_uid}
```

### Возврат платежа

```http
POST /api/v1/refund/{rq_uid}
Content-Type: application/json

{
    "amount": "250.00"  // Опционально, по умолчанию полная сумма
}
```

### Webhook уведомления

```http
POST /api/v1/callback
Content-Type: application/json
X-Signature: webhook_signature

{
    "order_id": "a67b0ced-c9a4-4cfb-bce3-b9595afaafc1",
    "status": 2,
    "error_code": null,
    "error_message": null
}
```

## Статусы платежей

| Статус | Описание |
|--------|----------|
| `CREATED` | Платеж создан |
| `ON_PAYMENT` | Платеж в обработке |
| `PAID` | Платеж оплачен (отправляется фискальный чек) |
| `DECLINED` | Платеж отклонен/отменен |
| `REFUNDED` | Платеж возвращен |
| `AUTHORIZED` | Платеж авторизован |
| `EXPIRED` | Истек срок действия |

## База данных

### Таблица PAY_SBP_LOG2
Основная таблица для логирования всех операций с платежами СБП.

### Таблица FEE
Таблица для учета платежей с проверкой дублей перед фискализацией.


## Управление через Makefile

```bash
make help          # Показать все команды
make up            # Запустить сервисы
make down          # Остановить сервисы
make logs          # Показать логи
make shell         # Войти в контейнер
make mysql         # MySQL консоль
make test          # Тестирование API
make clean         # Очистить данные
```

## Разработка

### Локальный запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск в режиме разработки
make dev
# или
uvicorn app.main:app --reload
```

### Проверка кода

```bash
make lint          # Проверка кода
make format        # Форматирование
```

## Фискализация АТОЛ

При получении статуса `PAID` автоматически:

1. Проверяется наличие дублей в таблице `FEE`
2. Если дублей нет, создается запись в `FEE`
3. Отправляется POST запрос на фискализацию в АТОЛ
4. Логируется результат операции

**Формат запроса к АТОЛ:**
```json
{
    "login": "atol_login",
    "hash": "sha1(md5(login + password + timestamp))",
    "timestamp": 1640995200,
    "payment_id": "SBP",
    "pin": "054350",
    "external_id": "123",
    "operation": "sell",
    "email": "user@example.com",
    "phone": "+79001234567",
    "receipt": [
        {
            "price": 500.00,
            "quantity": 1.000
        }
    ]
}
```

## Логирование

Логирование настроено с ежедневной ротацией файлов:
- Новый лог-файл создается каждый день в полночь
- Старые логи хранятся 30 дней
- Логи записываются в директорию `logs/` (защищена от внешнего доступа)
- Формат: `app.log` (текущий) и `app.log.YYYY-MM-DD` (архивные)

Все операции логируются в упрощенном формате для лучшей читаемости:

```
2025-10-22 12:00:00 - INFO - Callback received
2025-10-22 12:00:01 - INFO - Callback processed
```

## Безопасность

- Валидация всех входящих данных через Pydantic
- Обработка всех типов исключений
- Проверка подписи webhook уведомлений
- Использование HTTPS в продакшене
- Хранение секретов в переменных окружения
- Конфиденциальные файлы (.env) защищены через .gitignore
- API документация автоматически отключается в продакшене
- Автоматические миграции базы данных отключены для безопасности
- Валидация всех callback данных через Pydantic схемы

## Тестирование

```bash
# Тестирование создания платежа
make test

# Ручное тестирование через curl
curl -X POST http://localhost:8000/api/v1/create \
  -H "Content-Type: application/json" \
  -d '{"amount":"500","email":"test@example.com","account":"054350"}'
```

## Мониторинг

- Структурированные логи для анализа
- Метрики через FastAPI middleware
- Health check endpoint: `/health`
- Документация API: `/docs`

## Поддержка

При возникновении проблем:

1. Проверьте логи: `make logs`
2. Убедитесь в правильности настроек в `.env`
3. Проверьте доступность внешних сервисов (Сбербанк, АТОЛ)
4. Обратитесь к документации API: http://localhost:8000/docs

---

**Документация Сбербанка**: https://ecomtest.sberbank.ru/doc