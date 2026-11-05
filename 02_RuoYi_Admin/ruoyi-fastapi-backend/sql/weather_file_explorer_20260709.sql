-- 气象数据管理文件资源管理器兼容字段
-- 已有数据库执行本文件即可；全量重建库可直接导入 ruoyi-fastapi.sql。

SET @schema_name = DATABASE();

SET @item_type_exists = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'weather_file'
    AND COLUMN_NAME = 'item_type'
);
SET @sql = IF(
  @item_type_exists = 0,
  'ALTER TABLE weather_file ADD COLUMN item_type varchar(20) NULL DEFAULT ''file'' COMMENT ''资源类型：file/folder'' AFTER id',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @parent_id_exists = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'weather_file'
    AND COLUMN_NAME = 'parent_id'
);
SET @sql = IF(
  @parent_id_exists = 0,
  'ALTER TABLE weather_file ADD COLUMN parent_id bigint NULL DEFAULT 0 COMMENT ''父级目录ID，0为根目录'' AFTER item_type',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE weather_file
SET item_type = 'file'
WHERE item_type IS NULL OR item_type = '';

UPDATE weather_file
SET parent_id = 0
WHERE parent_id IS NULL;
