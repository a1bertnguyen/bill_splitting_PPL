-- ============================================================================
-- SplitLang MySQL 8.x / 9.x Schema & Least-Privilege App User Setup
-- Run once as MySQL root/admin:
--   "C:\Program Files\MySQL\MySQL Server 9.4\bin\mysql.exe" -u root -p < sql/init_mysql.sql
--
-- IMPORTANT: Replace 'ChangeMe_StrongAppPass!2026' below with a strong password
--            and put the exact same password in your local `.env` (MYSQL_PASSWORD).
-- ============================================================================

CREATE DATABASE IF NOT EXISTS splitlang_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Control #3 (Least-Privilege DB Account): Dedicated app user with DML-only privileges
-- (no DROP DATABASE, no GRANT, no FILE, no SUPER privileges).
CREATE USER IF NOT EXISTS 'splitlang_app'@'127.0.0.1'
  IDENTIFIED BY 'ChangeMe_StrongAppPass!2026';
CREATE USER IF NOT EXISTS 'splitlang_app'@'localhost'
  IDENTIFIED BY 'ChangeMe_StrongAppPass!2026';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, REFERENCES
  ON splitlang_db.* TO 'splitlang_app'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, REFERENCES
  ON splitlang_db.* TO 'splitlang_app'@'localhost';
FLUSH PRIVILEGES;

USE splitlang_db;

-- Users table (Control #10 Argon2id password_hash, Control #5 encrypted email_enc)
CREATE TABLE IF NOT EXISTS users (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    email_enc     TEXT         NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(16)  NOT NULL DEFAULT 'user',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Server-side sessions (Control #6, #9: opaque hashed session token, HttpOnly cookie)
CREATE TABLE IF NOT EXISTS sessions (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id       BIGINT UNSIGNED NOT NULL,
    token_hash    CHAR(64)        NOT NULL UNIQUE,
    csrf_token    CHAR(64)        NOT NULL,
    expires_at    DATETIME        NOT NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sessions_user (user_id),
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Groups table (Control #4 Row-Level Isolation via owner_user_id)
CREATE TABLE IF NOT EXISTS `groups` (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    name          VARCHAR(120)    NOT NULL,
    currency      VARCHAR(8)      NOT NULL DEFAULT 'VND',
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_group_owner_name (owner_user_id, name),
    INDEX idx_groups_owner (owner_user_id),
    CONSTRAINT fk_groups_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS members (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    group_id      BIGINT UNSIGNED NOT NULL,
    name          VARCHAR(64)     NOT NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_member_group_name (group_id, name),
    INDEX idx_members_owner_group (owner_user_id, group_id),
    CONSTRAINT fk_members_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS expenses (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_user_id   BIGINT UNSIGNED NOT NULL,
    group_id        BIGINT UNSIGNED NOT NULL,
    kind            VARCHAR(16)     NOT NULL DEFAULT 'expense',
    payer           VARCHAR(64)     NOT NULL,
    description_enc TEXT            NOT NULL,
    subtotal        VARCHAR(40)     NOT NULL,
    tax_amount      VARCHAR(40)     NOT NULL DEFAULT '0',
    tip_amount      VARCHAR(40)     NOT NULL DEFAULT '0',
    discount        VARCHAR(40)     NOT NULL DEFAULT '0',
    total           VARCHAR(40)     NOT NULL,
    split_mode      VARCHAR(24)     NOT NULL,
    items_enc       MEDIUMTEXT      NULL,
    expense_date    VARCHAR(16)     NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_expenses_owner_group (owner_user_id, group_id),
    CONSTRAINT fk_expenses_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS expense_shares (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    expense_id    BIGINT UNSIGNED NOT NULL,
    member_name   VARCHAR(64)     NOT NULL,
    share_amount  VARCHAR(40)     NOT NULL,
    INDEX idx_shares_expense (expense_id),
    CONSTRAINT fk_shares_expense FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS settlements (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    group_id      BIGINT UNSIGNED NOT NULL,
    from_member   VARCHAR(64)     NOT NULL,
    to_member     VARCHAR(64)     NOT NULL,
    amount        VARCHAR(40)     NOT NULL,
    note_enc      TEXT            NOT NULL,
    settle_date   VARCHAR(16)     NOT NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_settlements_owner_group (owner_user_id, group_id),
    CONSTRAINT fk_settlements_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS action_log (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    group_id      BIGINT UNSIGNED NOT NULL,
    action_type   VARCHAR(24)     NOT NULL,
    record_id     BIGINT UNSIGNED NOT NULL,
    summary_enc   TEXT            NOT NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_log_owner_group (owner_user_id, group_id),
    CONSTRAINT fk_log_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
) ENGINE=InnoDB;
