-- Инициализация базы данных СБП API

-- Создание таблицы для логирования callback уведомлений
CREATE TABLE IF NOT EXISTS CALLBACK_LOG (
    callback_id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Уникальный идентификатор записи',
    md_order VARCHAR(100) NOT NULL COMMENT 'Уникальный номер заказа в Платежном шлюзе',
    order_number VARCHAR(100) NOT NULL COMMENT 'Уникальный номер заказа в системе Партнера',
    operation VARCHAR(50) NOT NULL COMMENT 'Тип операции',
    status INT NOT NULL COMMENT 'Статус операции callback',
    additional_params VARCHAR(1000) NULL COMMENT 'Дополнительные параметры в JSON',
    received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Время получения callback',
    remote_addr VARCHAR(50) NULL COMMENT 'IP адрес отправителя',
    user_agent VARCHAR(255) NULL COMMENT 'User-Agent отправителя',
    processed INT NOT NULL DEFAULT 0 COMMENT 'Флаг обработки (0 - не обработан, 1 - обработан)',
    INDEX idx_md_order (md_order),
    INDEX idx_order_number (order_number),
    INDEX idx_received_at (received_at),
    INDEX idx_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Логирование входящих callback уведомлений';
