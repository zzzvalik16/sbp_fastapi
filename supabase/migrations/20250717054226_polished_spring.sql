-- Создание базы данных и пользователя
CREATE DATABASE IF NOT EXISTS sbp_api CHARACTER SET utf8 COLLATE utf8_general_ci;

-- Создание пользователя для приложения
CREATE USER IF NOT EXISTS 'sbp_user'@'%' IDENTIFIED BY 'sbp_password';
GRANT ALL PRIVILEGES ON sbp_api.* TO 'sbp_user'@'%';
FLUSH PRIVILEGES;

USE sbp_api;

-- Создание таблицы PAY_SBP_LOG2
CREATE TABLE IF NOT EXISTS `PAY_SBP_LOG2` (
    `sbp_id` INT(11) NOT NULL AUTO_INCREMENT,
    `uid` INT(6) NULL DEFAULT NULL COMMENT 'Уникальный идентификатор пользователя биллинга',
    `account` VARCHAR(6) NOT NULL DEFAULT '' COLLATE 'utf8_general_ci',
    `rq_uid` VARCHAR(32) NULL DEFAULT NULL COMMENT 'Уникальный идентификатор запроса' COLLATE 'utf8_general_ci',
    `order_sum` FLOAT(12) NULL DEFAULT NULL COMMENT 'Сумма заказа в минимальных единицах Валюты',
    `order_create_date` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Дата/время формирования заказа',
    `order_id` VARCHAR(36) NULL DEFAULT NULL COMMENT 'ID заказа в АС ППРБ.Карты' COLLATE 'utf8_general_ci',
    `order_state` ENUM('PAID','CREATED','REVERSED','REFUNDED','REVOKED','DECLINED','EXPIRED','AUTHORIZED','CONFIRMED','ON_PAYMENT') NULL DEFAULT NULL COMMENT 'Статус заказа' COLLATE 'utf8_general_ci',
    `order_form_url` VARCHAR(256) NULL DEFAULT NULL COMMENT 'Ссылка на считывание QR code' COLLATE 'utf8_general_ci',
    `rq_tm` TIMESTAMP NULL DEFAULT NULL COMMENT 'Дата/время формирования запроса',
    `operationDateTime` TIMESTAMP NULL DEFAULT NULL COMMENT 'Дата/время операции',
    `error_code` CHAR(6) NULL DEFAULT NULL COMMENT 'Код выполнения запроса' COLLATE 'utf8_general_ci',
    `error_description` VARCHAR(256) NULL DEFAULT NULL COMMENT 'Описание ошибки выполнения запроса' COLLATE 'utf8_general_ci',
    `source_payments` VARCHAR(10) NULL DEFAULT 'sbpStat' COLLATE 'utf8_general_ci',
    `fiscal_email` VARCHAR(100) NULL DEFAULT NULL COLLATE 'utf8_general_ci',
    `fiscal_phone` VARCHAR(12) NULL DEFAULT NULL COLLATE 'utf8_general_ci',
    PRIMARY KEY (`sbp_id`) USING BTREE,
    INDEX `trans_id` (`rq_uid`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

-- Создание таблицы FEE
CREATE TABLE IF NOT EXISTS `FEE` (
    `fid` INT(11) NOT NULL AUTO_INCREMENT,
    `uid` INT(11) NOT NULL,
    `date_pay` DATETIME NOT NULL,
    `sum_paid` DECIMAL(10,2) NOT NULL,
    `method` INT(11) NOT NULL,
    `comment` VARCHAR(255) NULL DEFAULT NULL COLLATE 'utf8_general_ci',
    `ticket_id` VARCHAR(20) NOT NULL COLLATE 'utf8_general_ci',
    PRIMARY KEY (`fid`) USING BTREE,
    UNIQUE INDEX `XPKFEE` (`uid`, `fid`) USING BTREE,
    INDEX `fee_uid` (`uid`) USING BTREE,
    INDEX `date_pay` (`date_pay`) USING BTREE,
    INDEX `ticket_id` (`ticket_id`) USING BTREE,
    INDEX `comment` (`comment`) USING BTREE,
    INDEX `method` (`method`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;