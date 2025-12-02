# Ограничение доступа к callback по IP адресам

## Описание

Роут `/api/v1/callback` теперь обрабатывается только при запросах с определённых IP адресов Сбербанка:
- `84.252.147.143`
- `185.157.97.241`

## Как это работает

### 1. Конфигурация (app/api/dependencies.py)

```python
ALLOWED_CALLBACK_IPS = {
    "84.252.147.143",
    "185.157.97.241"
}
```

### 2. Функция проверки (app/api/dependencies.py)

```python
async def verify_callback_ip(request: Request) -> Request:
    """
    Проверка IP адреса для callback уведомлений
    Разрешены только запросы с определённых IP адресов Сбербанка
    """
    client_ip = request.client.host if request.client else None
    
    if not client_ip:
        raise HTTPException(status_code=403, detail="Unable to verify client IP")
    
    if client_ip not in ALLOWED_CALLBACK_IPS:
        logger.warning("Callback request from unauthorized IP", client_ip=client_ip)
        raise HTTPException(status_code=403, detail="Access denied")
    
    logger.info("Callback IP verified", client_ip=client_ip)
    return request
```

### 3. Использование в endpoint (app/api/v1/endpoints/callback.py)

```python
@router.post("/callback")
async def handle_payment_callback(
    callback_data: CallbackPaymentData,
    payment_service: Annotated[PaymentService, Depends(get_payment_service_safe)],
    request: Annotated[Request, Depends(verify_callback_ip)]  # ← Проверка IP
) -> dict[str, str]:
    # Обработка callback...
```

## Поведение

### ✅ Разрешённые запросы
Запросы с IP `84.252.147.143` или `185.157.97.241`:
- Проходят проверку
- Логируется: `"Callback IP verified", client_ip=...`
- Обрабатываются как обычно

### ❌ Запрещённые запросы
Запросы с любых других IP адресов:
- Отклоняются с ошибкой `HTTP 403 Forbidden`
- Логируется: `"Callback request from unauthorized IP", client_ip=...`
- Ответ: `{"detail": "Access denied"}`

### ❌ Невозможно определить IP
Если IP адрес не может быть определен:
- Отклоняется с ошибкой `HTTP 403 Forbidden`
- Логируется: `"Unable to determine client IP address"`
- Ответ: `{"detail": "Unable to verify client IP"}`

## Логирование

### Успешная проверка
```json
{
  "event": "Callback IP verified",
  "level": "info",
  "client_ip": "84.252.147.143"
}
```

### Неавторизованный IP
```json
{
  "event": "Callback request from unauthorized IP",
  "level": "warning",
  "client_ip": "192.168.1.100"
}
```

## Добавление новых IP адресов

Чтобы добавить новый IP адрес Сбербанка, отредактируйте `app/api/dependencies.py`:

```python
ALLOWED_CALLBACK_IPS = {
    "84.252.147.143",
    "185.157.97.241",
    "NEW_IP_ADDRESS"  # ← Добавить здесь
}
```

## Примечания

1. **X-Forwarded-For**: Если приложение находится за прокси (nginx, load balancer), может потребоваться дополнительная конфигурация для правильного определения реального IP адреса клиента.

2. **Тестирование**: При локальном тестировании IP будет `127.0.0.1` или `localhost`, что не в списке разрешённых. Используйте специальный инструмент для имитации запроса с нужного IP адреса.

3. **Безопасность**: Проверка IP выполняется на уровне dependency injection, что обеспечивает её выполнение ДО обработки callback.

## Обработка через прокси

Если приложение за прокси, нужно настроить FastAPI для доверия прокси заголовкам:

```python
# В app/main.py
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["84.252.147.143", "185.157.97.241"]
)
```

Или использовать `X-Forwarded-For` заголовок в verify_callback_ip:

```python
async def verify_callback_ip(request: Request) -> Request:
    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.client.host if request.client else None
    # ...
```
