# Makefile для управления FastAPI СБП API

.PHONY: help build up down restart logs shell mysql clean install test

help: ## Показать справку
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$\' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Собрать Docker образы
	docker-compose -f docker/docker-compose.yml build

up: ## Запустить все сервисы
	docker-compose -f docker/docker-compose.yml up -d
	@echo "Сервисы запущены:"
	@echo "  - API: http://localhost:8000"
	@echo "  - Docs: http://localhost:8000/docs (только в DEBUG режиме)"
	@echo "  - phpMyAdmin: http://localhost:8080"
	@echo "  - MySQL: localhost:3306"

down: ## Остановить все сервисы
	docker-compose -f docker/docker-compose.yml down

restart: ## Перезапустить все сервисы
	docker-compose -f docker/docker-compose.yml restart

logs: ## Показать логи всех сервисов
	docker-compose -f docker/docker-compose.yml logs -f

logs-app: ## Показать логи приложения
	docker-compose -f docker/docker-compose.yml logs -f app

logs-mysql: ## Показать логи MySQL
	docker-compose -f docker/docker-compose.yml logs -f mysql

shell: ## Войти в контейнер приложения
	docker-compose -f docker/docker-compose.yml exec app bash

mysql: ## Войти в MySQL консоль
	docker-compose -f docker/docker-compose.yml exec mysql mysql -u root -proot_password sbp_api

clean: ## Очистить все данные и образы
	docker-compose -f docker/docker-compose.yml down -v
	docker system prune -f

install: ## Первоначальная установка
	@echo "Установка FastAPI СБП API..."
	@make build
	@make up
	@echo "Ожидание готовности сервисов..."
	@sleep 15
	@echo "Установка завершена!"
	@echo "API доступен по адресу: http://localhost:8000"
	@echo "Документация: http://localhost:8000/docs"
	@echo "phpMyAdmin: http://localhost:8080 (root/root_password)"

test: ## Тестирование API
	@echo "Тестирование создания платежа..."
	@curl -X POST http://localhost:8000/api/v1/payment/create \
		-H "Content-Type: application/json\" \
		-d '{"amount":"500","email":"test@example.com","account":"054350","paymentStat":"sbpStat"}\' \
		| python -m json.tool

status: ## Показать статус сервисов
	docker-compose -f docker/docker-compose.yml ps

dev: ## Запуск в режиме разработки
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

requirements: ## Обновить requirements.txt
	pip freeze > requirements.txt

lint: ## Проверка кода
	flake8 app/
	mypy app/

format: ## Форматирование кода
	black app/
	isort app/