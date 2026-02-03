# Docker развертывание приложения SBP API

## Требования

- Docker и Docker Compose установлены
- Доступ к удалённой MySQL БД
- Учетные данные Сбербанка API
- Учетные данные АТОЛ API

## Архитектура

```
┌─────────────────────────────────────┐
│   Docker контейнер (FastAPI)        │
│   - приложение                      │
│   - обработка платежей              │
│   - отправка чеков в АТОЛ           │
└─────────────────────────────────────┘
            ↓
    ┌───────────────────┐
    │   Удалённая       │
    │   MySQL БД        │
    │   (ваш хост)      │
    └───────────────────┘

    ↓                ↓
┌───────────┐  ┌──────────────┐
│ Сбербанк  │  │ АТОЛ (чеки)  │
│ (платежи) │  │              │
└───────────┘  └──────────────┘
```

## Быстрый старт

### 1. Подготовка окружения

Скопируйте `.env.example` или используйте `.env`:

```bash
# .env расположен в корне проекта
```

### 2. Настройте обязательные переменные в `.env`

#### База данных MySQL (обязательно):

```env
DB_HOST=your_remote_db_host          # IP или доменное имя удалённой БД
DB_PORT=3306                         # Стандартный порт MySQL
DB_USER=your_db_user                 # Пользователь БД
DB_PASSWORD=your_db_password         # Пароль БД
DB_NAME=your_db_name                 # Имя базы данных
```

#### Сбербанк API (обязательно):

```env
SBERBANK_USERNAME=your_username      # Логин в личном кабинете Сбербанка
SBERBANK_PASSWORD=your_password      # Пароль Сбербанка
SBERBANK_RETURN_URL=https://your-domain.com/return
SBERBANK_FAIL_RETURN_URL=https://your-domain.com/return
TEST_MODE=true                       # true = тест, false = продакшн
```

#### АТОЛ API (обязательно для чеков):

```env
ATOL_LOGIN=your_atol_login           # Логин АТОЛ
ATOL_PASSWORD=your_atol_password     # Пароль АТОЛ
```

#### Безопасность:

```env
CALLBACK_SECRET=your_secret          # Минимум 32 символа
```

### 3. Сертификат Сбербанка (опционально)

Если есть сертификат цепи Сбербанка:

```bash
mkdir -p certs
cp your_sberbank_chain.pem certs/sberbank_chain.pem
```

Если не добавить - используются системные сертификаты.

### 4. Запуск контейнера

```bash
# Из директории проекта (где docker-compose.yml)
docker-compose up -d

# Логи
docker-compose logs -f app

# Остановка
docker-compose down
```

Приложение доступно на: **http://localhost:8000**

## Проверка работы

### 1. Здоровье приложения

```bash
curl http://localhost:8000/docs
```

Должна открыться документация Swagger.

### 2. Подключение к БД

```bash
# Проверьте логи
docker-compose logs app | grep -i "database\|connection"
```

Ищите сообщение: `Database connection established`

### 3. Сбербанк API

Выполните тестовый запрос платежа через API.

### 4. АТОЛ фискализация

Проверьте в логах отправку чеков в АТОЛ.

## Режимы

### Тестовый режим (по умолчанию)

```env
TEST_MODE=true
```

Использует:
- Тестовый URL Сбербанка
- Тестовый режим АТОЛ
- Упрощенная логирование

### Production режим

```env
TEST_MODE=false
DEBUG=false
LOG_LEVEL=WARNING
VERIFY_SSL=true
```

Использует:
- Production URL Сбербанка
- Production АТОЛ
- Минимальное логирование

## Переменные окружения

| Переменная | Обязательно | Описание |
|---|---|---|
| `DB_HOST` | ✅ | Хост удалённой MySQL |
| `DB_PORT` | ❌ | Порт (по умолчанию 3306) |
| `DB_USER` | ✅ | Пользователь БД |
| `DB_PASSWORD` | ✅ | Пароль БД |
| `DB_NAME` | ✅ | Имя БД |
| `SBERBANK_USERNAME` | ✅ | Логин Сбербанка |
| `SBERBANK_PASSWORD` | ✅ | Пароль Сбербанка |
| `SBERBANK_RETURN_URL` | ✅ | URL возврата при успехе |
| `SBERBANK_FAIL_RETURN_URL` | ✅ | URL при ошибке |
| `ATOL_LOGIN` | ✅ | Логин АТОЛ |
| `ATOL_PASSWORD` | ✅ | Пароль АТОЛ |
| `CALLBACK_SECRET` | ✅ | Secret для callback |
| `TEST_MODE` | ❌ | true/false (по умолчанию true) |
| `DEBUG` | ❌ | true/false (по умолчанию false) |
| `LOG_LEVEL` | ❌ | INFO, WARNING, ERROR (по умолчанию INFO) |
| `VERIFY_SSL` | ❌ | true/false (по умолчанию false) |

## Диагностика проблем

### Ошибка: "Cannot connect to MySQL"

```bash
# 1. Проверьте доступ к БД
mysql -h your_db_host -u your_db_user -p

# 2. Убедитесь в правильности хоста
ping your_db_host

# 3. Проверьте переменные в .env
cat .env | grep DB_

# 4. Логи контейнера
docker-compose logs app | grep -i error
```

### Ошибка: "Sberbank API failed"

```bash
# 1. Проверьте логин/пароль
cat .env | grep SBERBANK_

# 2. Убедитесь что TEST_MODE соответствует вашему аккаунту
cat .env | grep TEST_MODE

# 3. Проверьте доступ в интернет из контейнера
docker-compose exec app curl -I https://ecomift.sberbank.ru
```

### Ошибка: "ATOL check failed"

```bash
# 1. Проверьте учетные данные
cat .env | grep ATOL_

# 2. Убедитесь что ATOL_URL доступен
docker-compose exec app curl -I https://atol.starlink.ru
```

### Ошибка: "Connection refused" на порту 8000

```bash
# Проверьте что порт не занят
lsof -i :8000

# Или используйте другой порт в docker-compose.yml
# ports:
#   - "9000:8000"
```

## Логирование

```bash
# Последние 100 строк логов
docker-compose logs --tail 100 app

# Следить за логами в реальном времени
docker-compose logs -f app

# Логи за последние 5 минут
docker-compose logs --since 5m app

# Только ошибки (grep)
docker-compose logs app | grep ERROR
```

## Volumes и файлы

Контейнер сохраняет:

- `/app/logs/` → `./logs/` (логи приложения)
- `/app/certs/` → `./certs/` (сертификаты Sberbank, read-only)

## Обновление контейнера

```bash
# Пересборка образа с новым кодом
docker-compose up -d --build

# Перезапуск контейнера
docker-compose restart app

# Полная переустановка
docker-compose down
docker-compose up -d --build
```

## Security

- Никогда не коммитьте `.env` в репозиторий
- Используйте strong passwords для CALLBACK_SECRET
- Для production используйте SSL certificates
- Ограничьте ALLOWED_ORIGINS и ALLOWED_CALLBACK_IPS
- Используйте VERIFY_SSL=true в production

## Support

При возникновении проблем:

1. Проверьте логи: `docker-compose logs app`
2. Проверьте переменные: `cat .env`
3. Убедитесь в доступности всех внешних сервисов
4. Проверьте firewall правила для доступа к БД
