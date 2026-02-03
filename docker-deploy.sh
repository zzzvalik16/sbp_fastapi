#!/bin/bash

set -e

echo "=== SBP API Docker Deployment Setup ==="
echo

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose."
    exit 1
fi

echo "✅ Docker и Docker Compose установлены"
echo

# Проверка .env
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не найден"

    if [ -f .env.example ]; then
        echo "📋 Создаю .env из .env.example..."
        cp .env.example .env
        echo "✅ Файл .env создан"
    else
        echo "❌ .env.example не найден"
        exit 1
    fi
else
    echo "✅ Файл .env существует"
fi

echo

# Проверка обязательных переменных
echo "🔍 Проверка конфигурации..."

required_vars=(
    "DB_HOST"
    "DB_USER"
    "DB_PASSWORD"
    "DB_NAME"
    "SBERBANK_USERNAME"
    "SBERBANK_PASSWORD"
    "SBERBANK_RETURN_URL"
    "ATOL_LOGIN"
    "ATOL_PASSWORD"
    "CALLBACK_SECRET"
)

missing_vars=()

for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" .env || grep -q "^$var=your_" .env; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "❌ Обязательные переменные не заполнены:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo
    echo "📝 Отредактируйте .env и заполните значения:"
    echo "   nano .env"
    echo
    exit 1
fi

echo "✅ Все обязательные переменные заполнены"
echo

# Создание директорий
echo "📁 Создание директорий..."
mkdir -p logs certs
echo "✅ Директории готовы"
echo

# Проверка доступа к БД (опционально)
read -p "Проверить доступ к базе данных перед запуском? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔗 Проверка подключения к БД..."

    DB_HOST=$(grep "^DB_HOST=" .env | cut -d'=' -f2)
    DB_USER=$(grep "^DB_USER=" .env | cut -d'=' -f2)

    if command -v mysql &> /dev/null; then
        if mysql -h "$DB_HOST" -u "$DB_USER" -p -e "SELECT 1" &>/dev/null; then
            echo "✅ Соединение с БД успешно"
        else
            echo "⚠️  Не удалось подключиться к БД"
            read -p "Продолжить без проверки? (y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    else
        echo "⚠️  mysql-client не установлен, пропускаю проверку"
    fi
    echo
fi

# Запуск контейнера
echo "🚀 Запуск контейнера..."
docker-compose up -d --build

echo
echo "✅ Контейнер запущен!"
echo

# Ожидание запуска приложения
echo "⏳ Ожидание готовности приложения (максимум 60 секунд)..."
max_attempts=60
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
        echo "✅ Приложение готово!"
        break
    fi

    attempt=$((attempt + 1))
    echo -n "."
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo
    echo "⚠️  Приложение не ответило за отведённое время"
    echo "📋 Проверьте логи: docker-compose logs app"
fi

echo
echo "========================================="
echo "✅ Развертывание завершено!"
echo "========================================="
echo
echo "📍 Приложение доступно на: http://localhost:8000"
echo "📖 Документация API: http://localhost:8000/docs"
echo
echo "📝 Полезные команды:"
echo "   - Логи: docker-compose logs -f app"
echo "   - Остановка: docker-compose down"
echo "   - Перезапуск: docker-compose restart app"
echo "   - Обновление кода: docker-compose up -d --build"
echo
echo "💡 Подробнее: cat DOCKER_DEPLOYMENT.md"
echo
