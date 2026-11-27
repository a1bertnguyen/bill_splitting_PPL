-- ============================================================================
-- SplitLang MySQL Schema for Docker (/docker-entrypoint-initdb.d/01_schema.sql)
-- Note: Database and least-privilege user (MYSQL_USER / MYSQL_PASSWORD) are
--       created automatically by the official mysql:8.4 image from `.env`.
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    email_enc     TEXT         NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(16)  NOT NULL DEFAULT 'user',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sessions (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id       BIGINT UNSIGNED NOT NULL,
    token_hash    CHAR(64)        NOT NULL UNIQUE,
    csrf_token    CHAR(64)        NOT NULL,
    expires_at    DATETIME        NOT NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sessions_user (user_id),
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `groups` (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    name          VARCHAR(120)    NOT NULL,
    currency      VARCHAR(8)      NOT NULL DEFAULT 'VND',
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_group_owner_name (owner_user_id, name),
    INDEX idx_groups_owner (owner_user_id),
    CONSTRAINT fk_groups_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS members (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    group_id      BIGINT UNSIGNED NOT NULL,
    name          VARCHAR(64)     NOT NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_member_group_name (group_id, name),
    INDEX idx_members_owner_group (owner_user_id, group_id),
    CONSTRAINT fk_members_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS expense_shares (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    expense_id    BIGINT UNSIGNED NOT NULL,
    member_name   VARCHAR(64)     NOT NULL,
    share_amount  VARCHAR(40)     NOT NULL,
    INDEX idx_shares_expense (expense_id),
    CONSTRAINT fk_shares_expense FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
