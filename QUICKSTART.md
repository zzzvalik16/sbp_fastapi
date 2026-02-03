# Быстрый старт Docker

## За 5 минут до запуска

### 1. Заполните .env (1 минута)

```bash
cp .env.example .env
nano .env
```

**Обязательные поля:**

```env
# Ваша удалённая MySQL
DB_HOST=db.example.com
DB_USER=user
DB_PASSWORD=password
DB_NAME=sbp_api

# Сбербанк
SBERBANK_USERNAME=username
SBERBANK_PASSWORD=password

# АТОЛ чеки
ATOL_LOGIN=login
ATOL_PASSWORD=password

# Callback
CALLBACK_SECRET=very_long_secret_min_32_chars
```

### 2. Запустите скрипт развертывания

```bash
bash docker-deploy.sh
```

Скрипт:
- ✅ Проверит Docker и Docker Compose
- ✅ Создаст необходимые директории
- ✅ Выполнит построение и запуск контейнера
- ✅ Проверит готовность приложения

### 3. Проверьте доступ

```bash
curl http://localhost:8000/docs
```

Откроется Swagger документация API.

## Команды

```bash
# Логи приложения
docker-compose logs -f app

# Остановить контейнер
docker-compose down

# Перезапустить контейнер
docker-compose restart app

# Пересобрать с новым кодом
docker-compose up -d --build
```

## Типичные проблемы

### "Connection refused to MySQL"

1. Проверьте DB_HOST - должен быть доступен из интернета
2. Убедитесь в правильности учетных данных
3. Проверьте firewall - порт 3306 открыт?

```bash
mysql -h DB_HOST -u DB_USER -p
```

### "Sberbank API error"

1. Проверьте SBERBANK_USERNAME и SBERBANK_PASSWORD
2. Убедитесь TEST_MODE соответствует вашему аккаунту
3. Проверьте интернет из контейнера:

```bash
docker-compose exec app curl https://ecomift.sberbank.ru
```

### Приложение зависает на запуске

Обычно проблема в подключении к БД. Проверьте логи:

```bash
docker-compose logs app | tail -50
```

## Полная документация

Детальная информация: [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)

## Production развертывание

Для production измените в `.env`:

```env
DEBUG=false
LOG_LEVEL=WARNING
VERIFY_SSL=true
TEST_MODE=false
ALLOWED_ORIGINS=["https://your-domain.com"]
ALLOWED_CALLBACK_IPS=["185.166.131.134", "185.166.131.135"]
```

Плюс:
- Добавьте сертификат Sberbank в `certs/sberbank_chain.pem`
- Используйте strong CALLBACK_SECRET (минимум 32 символа)
- Настройте backups БД
- Настройте мониторинг логов
