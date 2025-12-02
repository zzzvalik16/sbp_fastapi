# Реализация ограничения доступа к callback по IP адресам

## Краткое описание

Роут `/api/v1/callback` теперь защищен от несанкционированного доступа через проверку IP адреса. Обрабатываются запросы только с двух IP адресов Сбербанка:
- `84.252.147.143`
- `185.157.97.241`

## Что было изменено

### 1. app/api/dependencies.py

**Добавлено:**
- Константа `ALLOWED_CALLBACK_IPS` со списком разрешённых IP адресов
- Функция `verify_callback_ip()` для проверки IP адреса клиента
- Импорты: `HTTPException`, `Request`, `status` из FastAPI, `structlog`

**Логика:**
```python
ALLOWED_CALLBACK_IPS = {
    "84.252.147.143",
    "185.157.97.241"
}

async def verify_callback_ip(request: Request) -> Request:
    # Получить IP из request.client.host
    # Проверить наличие IP
    # Проверить принадлежность к ALLOWED_CALLBACK_IPS
    # Вернуть 403 Forbidden если IP не разрешён
```

### 2. app/api/v1/endpoints/callback.py

**Изменено:**
- Добавлен импорт `verify_callback_ip` из dependencies
- Добавлена аннотация зависимости `verify_callback_ip` к параметру `request` в функции `handle_payment_callback`

**До:**
```python
async def handle_payment_callback(
    callback_data: CallbackPaymentData,
    payment_service: Annotated[PaymentService, Depends(get_payment_service_safe)],
    request: Request
) -> dict[str, str]:
```

**После:**
```python
async def handle_payment_callback(
    callback_data: CallbackPaymentData,
    payment_service: Annotated[PaymentService, Depends(get_payment_service_safe)],
    request: Annotated[Request, Depends(verify_callback_ip)]  # ← IP проверка
) -> dict[str, str]:
```

## Механизм работы

1. **При получении запроса к /api/v1/callback:**
   - FastAPI вызывает dependency `verify_callback_ip`
   - Функция извлекает IP адрес из `request.client.host`
   - Проверяет принадлежность IP к списку `ALLOWED_CALLBACK_IPS`

2. **Если IP разрешён:**
   - Логируется: `"Callback IP verified", client_ip=...` (уровень INFO)
   - Запрос продолжает обработку
   - Callback обрабатывается как обычно

3. **Если IP не разрешён:**
   - Логируется: `"Callback request from unauthorized IP", client_ip=...` (уровень WARNING)
   - Возвращается HTTP 403 Forbidden
   - Ответ: `{"detail": "Access denied"}`
   - Callback не обрабатывается

4. **Если IP не может быть определен:**
   - Логируется: `"Unable to determine client IP address"` (уровень WARNING)
   - Возвращается HTTP 403 Forbidden
   - Ответ: `{"detail": "Unable to verify client IP"}`

## Примеры HTTP ответов

### ✅ Успешный callback (IP разрешён)

```http
POST /api/v1/callback HTTP/1.1
Host: example.com
X-Forwarded-For: 84.252.147.143

{ "mdOrder": "123", ... }
```

Ответ:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "success", "message": "Callback processed"}
```

### ❌ Неавторизованный IP

```http
POST /api/v1/callback HTTP/1.1
Host: example.com
X-Forwarded-For: 192.168.1.100

{ "mdOrder": "123", ... }
```

Ответ:
```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{"detail": "Access denied"}
```

## Логирование

### Структурированные логи (structlog)

Успешная проверка:
```json
{
  "event": "Callback IP verified",
  "level": "info",
  "logger": "app.api.dependencies",
  "client_ip": "84.252.147.143",
  "timestamp": "2025-11-18 12:34:56"
}
```

Неавторизованный IP:
```json
{
  "event": "Callback request from unauthorized IP",
  "level": "warning",
  "logger": "app.api.dependencies",
  "client_ip": "192.168.1.100",
  "timestamp": "2025-11-18 12:34:57"
}
```

## Безопасность

### Достоинства:
1. ✅ Проверка выполняется на уровне dependency injection (ДО обработки данных)
2. ✅ Защита от несанкционированного доступа
3. ✅ Логирование попыток неавторизованного доступа
4. ✅ Простота добавления новых IP адресов
5. ✅ Асинхронная реализация без блокировок

### Рекомендации:
1. 🔒 Использовать HTTPS в production
2. 🔒 Если за прокси - настроить `X-Forwarded-For` обработку
3. 🔒 Регулярно проверять логи на попытки неавторизованного доступа
4. 🔒 Дублировать проверку IP на уровне firewall/WAF

## Модификация списка IP адресов

Для добавления/удаления IP адресов отредактируйте `app/api/dependencies.py`:

```python
ALLOWED_CALLBACK_IPS = {
    "84.252.147.143",
    "185.157.97.241",
    # Новые IP адреса добавить здесь
}
```

Изменения вступают в силу после перезапуска приложения.

## Конфигурация для прокси

Если приложение находится за nginx/load balancer, используйте X-Forwarded-For:

```python
# app/api/dependencies.py
async def verify_callback_ip(request: Request) -> Request:
    # Получить IP из X-Forwarded-For (для прокси)
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else None
    
    # ... остальной код
```

## Тестирование в развёртывании

Для проверки:
```bash
# Авторизованный IP
curl -X POST http://localhost:8000/api/v1/callback \
  -H "X-Forwarded-For: 84.252.147.143" \
  -H "Content-Type: application/json" \
  -d '{"mdOrder":"123","status":1}'

# Неавторизованный IP
curl -X POST http://localhost:8000/api/v1/callback \
  -H "X-Forwarded-For: 192.168.1.100" \
  -H "Content-Type: application/json" \
  -d '{"mdOrder":"123","status":1}'
```
