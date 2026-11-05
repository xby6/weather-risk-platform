-- Apply before deployment when the application DB user has no CREATE privilege.
CREATE TABLE IF NOT EXISTS algorithm_task_history (
    id bigint NOT NULL AUTO_INCREMENT PRIMARY KEY,
    task_code varchar(128) NOT NULL,
    task_status varchar(32) NOT NULL,
    progress int NOT NULL DEFAULT 0,
    message text,
    error_message text,
    event_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_history (task_code, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
