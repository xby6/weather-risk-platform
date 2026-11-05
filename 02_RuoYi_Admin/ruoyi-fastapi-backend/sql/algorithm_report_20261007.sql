-- Algorithm result AI report v1. Run in the application database before deployment.
-- Idempotent; no existing task or AI model data is changed.

CREATE TABLE IF NOT EXISTS algorithm_report_config (
        id int NOT NULL PRIMARY KEY,
        model_id bigint NULL,
        auto_enabled tinyint NOT NULL DEFAULT 0,
        auto_since varchar(32) NOT NULL DEFAULT '',
        instructions text,
        update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS algorithm_report (
        id varchar(36) NOT NULL PRIMARY KEY,
        task_code varchar(128) NOT NULL,
        source_key varchar(64) NOT NULL,
        version int NOT NULL DEFAULT 1,
        title varchar(255) NOT NULL,
        report_status varchar(20) NOT NULL DEFAULT 'queued',
        model_id bigint NOT NULL,
        model_info longtext NOT NULL,
        snapshot_json longtext NOT NULL,
        snapshot_path text,
        instructions text,
        facts_json longtext,
        prompt longtext,
        analysis_json longtext,
        content longtext,
        error_message text,
        attempts int NOT NULL DEFAULT 0,
        lease_token varchar(36),
        lease_until datetime,
        next_attempt_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        create_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_report_source_version (source_key, version),
        INDEX idx_report_task (task_code, create_time),
        INDEX idx_report_queue (report_status, next_attempt_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
