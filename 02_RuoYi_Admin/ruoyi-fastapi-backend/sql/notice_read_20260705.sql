-- 通知公告已读功能增量脚本
-- 适用于已经导入 ruoyi-fastapi.sql 的现有 MySQL 数据库。

CREATE TABLE IF NOT EXISTS `sys_notice_read` (
  `read_id` bigint NOT NULL AUTO_INCREMENT COMMENT '阅读记录ID',
  `notice_id` int NOT NULL COMMENT '公告ID',
  `reader_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '阅读者类型（screen/user）',
  `reader_key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '阅读者标识',
  `read_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '阅读时间',
  PRIMARY KEY (`read_id`) USING BTREE,
  UNIQUE KEY `uk_notice_reader` (`notice_id`, `reader_type`, `reader_key`) USING BTREE,
  KEY `idx_notice_read_notice_id` (`notice_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '通知公告阅读记录表' ROW_FORMAT = Dynamic;
