# Исправление ошибки таймаута при создании QR кода

## Проблема

При ожидании ответа от Сбербанка более 50 секунд возникала неопределённая ошибка:
```
"error": "catching classes that do not inherit from BaseException is not allowed"
```

Логи показывали:
```
2025-11-18 00:52:25 - app.services.payment_service - ERROR - create_payment:214 - 
{"error": "catching classes that do not inherit from BaseException is not allowed", ...}
```

## Причины ошибки

### 1. Неправильное имя исключения таймаута (sberbank_service.py:138)
- Использовалось `httpx.Timeout` вместо `httpx.TimeoutException`
- `httpx.Timeout` - это класс для параметров таймаута, не исключение
- При таймауте библиотека выбрасывает `httpx.TimeoutException`

### 2. Доступ к несуществующему атрибуту (sberbank_service.py:138)
- Попытка обращения к `e.request.timeout` в обработчике исключения
- При таймауте объект `request` может быть `None` или не существовать

### 3. Обработка общего Exception вместо BaseException (payment_service.py:214)
- Ловился `Exception`, но это не ловит системные ошибки
- Это привело к попытке обработать BaseException, что недопустимо

## Решение

### Изменения в sberbank_service.py

1. **Заменен тип исключения на все методы:**
   ```python
   # До:
   except httpx.Timeout as e:
       error=f"Request timed out after {e.request.timeout} seconds. {str(e)}"
   
   # После:
   except httpx.TimeoutException as e:
       error=f"Request timed out: {str(e)}"
   ```

2. **Добавлена правильная иерархия исключений для всех методов:**
   ```python
   except httpx.TimeoutException as e:  # Таймаут сети
   except httpx.HTTPStatusError as e:   # HTTP ошибки 4xx, 5xx
   except httpx.RequestError as e:      # Прочие сетевые ошибки
   except Exception as e:               # Неожиданные ошибки
   ```

3. **Исправлена обработка ошибок:**
   - Удалены попытки доступа к потенциально None атрибутам
   - Добавлено логирование типа ошибки: `error_type=type(e).__name__`
   - Улучшена читаемость логов

### Изменения в payment_service.py

1. **Добавлен импорт:**
   ```python
   import traceback
   ```

2. **Улучшена обработка исключений:**
   ```python
   except PaymentException:
       raise  # Пробросить свои исключения
   except Exception as e:
       logger.error(
           "Failed to create payment",
           error_type=type(e).__name__,
           error=str(e),
           traceback=traceback.format_exc()
       )
       raise PaymentException(f"Failed to create payment: {type(e).__name__}")
   ```

## Результат

Теперь при таймауте логируется ясная ошибка:
```
"Request timed out after 50 seconds"
```

При других сетевых ошибках логируется:
```
"Network error: ConnectError" или "Network error: TimeoutException"
```

При HTTP ошибках логируется:
```
"HTTP error 503: Service Unavailable"
```

## Методы, получившие исправления

### sberbank_service.py
- `create_qr_code()` - создание QR кода
- `get_payment_status()` - получение статуса платежа
- `cancel_payment()` - отмена платежа
- `refund_payment()` - возврат платежа

### payment_service.py
- `create_payment()` - создание платежа

## Тестирование

Для проверки исправления:
1. Остановить Сбербанк API (или задержать ответ на >50 сек)
2. Запустить запрос на создание платежа
3. Убедиться, что логируется: "Request timed out after 50 seconds"
4. Ответ содержит ясное сообщение об ошибке, а не "catching classes..."
