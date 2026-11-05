"""气象数据文件 MySQL 持久化服务。

所有气象数据文件记录从 weather_file 表读写，不再使用前端写死数据或本地 JSON 文件。
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

UPLOAD_DIR = Path('vf_admin/upload_path/weather_data')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

EXPLORER_COLUMNS = {
    'item_type': "ALTER TABLE weather_file ADD COLUMN item_type varchar(20) NULL DEFAULT 'file' COMMENT '资源类型：file/folder' AFTER id",
    'parent_id': "ALTER TABLE weather_file ADD COLUMN parent_id bigint NULL DEFAULT 0 COMMENT '父级目录ID，0为根目录' AFTER item_type",
}


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _size_text(size: int | None) -> str:
    size = int(size or 0)
    if size >= 1024 * 1024:
        return f'{size / 1024 / 1024:.2f}MB'
    if size >= 1024:
        return f'{size / 1024:.1f}KB'
    return f'{size}B'


def _progress_from_status(status: str | None) -> int:
    status = status or 'uploaded'
    if status in {'finished', 'imported'}:
        return 100
    if status in {'parsed'}:
        return 70
    if status in {'failed'}:
        return 100
    return 0


def _fields_to_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, list):
        return ', '.join([str(i) for i in value])
    text_value = str(value)
    try:
        parsed = json.loads(text_value)
        if isinstance(parsed, list):
            return ', '.join([str(i) for i in parsed])
    except Exception:
        pass
    return text_value


def _row_to_vo(row: Any) -> dict[str, Any]:
    m = row._mapping if hasattr(row, '_mapping') else row
    item_type = m.get('item_type') or 'file'
    status = m.get('process_status') or 'uploaded'
    return {
        'id': m.get('id'),
        'itemType': item_type,
        'isFolder': item_type == 'folder',
        'parentId': int(m.get('parent_id') or 0),
        'name': m.get('file_name') or m.get('original_name') or '',
        'originalName': m.get('original_name') or '',
        'dataType': m.get('data_type') or '',
        'fileType': m.get('file_type') or '',
        'region': m.get('region_name') or '',
        'stationOrLine': m.get('station_or_line') or '',
        'timeResolution': m.get('time_resolution') or '',
        'startTime': str(m.get('start_time') or ''),
        'endTime': str(m.get('end_time') or ''),
        'recordCount': m.get('record_count') or 0,
        'fieldCount': m.get('field_count') or 0,
        'fields': _fields_to_text(m.get('field_names')),
        'size': _size_text(m.get('file_size')),
        'fileSize': m.get('file_size') or 0,
        'filePath': m.get('file_path') or '',
        'status': status,
        'progress': _progress_from_status(status),
        'remark': m.get('remark') or '',
        'createBy': m.get('create_by') or '',
        'createTime': str(m.get('create_time') or ''),
        'updateTime': str(m.get('update_time') or ''),
    }


async def ensure_explorer_columns(db: AsyncSession) -> None:
    """Keep current databases compatible with the file-explorer UI."""
    for column_name, alter_sql in EXPLORER_COLUMNS.items():
        try:
            exists = await db.execute(text('''
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'weather_file'
                  AND COLUMN_NAME = :column_name
            '''), {'column_name': column_name})
            if int(exists.scalar() or 0) == 0:
                await db.execute(text(alter_sql))
                await db.commit()
        except Exception:
            await db.rollback()
            raise


async def list_files(db: AsyncSession) -> list[dict[str, Any]]:
    await ensure_explorer_columns(db)
    result = await db.execute(text('''
        SELECT id, item_type, parent_id, file_name, original_name, file_type, data_type, region_name, station_or_line,
               time_resolution, start_time, end_time, record_count, field_count, field_names,
               file_size, file_path, process_status, remark, create_by, create_time, update_time
        FROM weather_file
        ORDER BY create_time DESC, id DESC
    '''))
    return [_row_to_vo(row) for row in result.fetchall()]


async def get_file(db: AsyncSession, file_id: str | int) -> dict[str, Any] | None:
    await ensure_explorer_columns(db)
    result = await db.execute(text('''
        SELECT id, item_type, parent_id, file_name, original_name, file_type, data_type, region_name, station_or_line,
               time_resolution, start_time, end_time, record_count, field_count, field_names,
               file_size, file_path, process_status, remark, create_by, create_time, update_time
        FROM weather_file
        WHERE id = :id
        LIMIT 1
    '''), {'id': int(file_id)})
    row = result.fetchone()
    return _row_to_vo(row) if row else None


async def save_file(db: AsyncSession, row: dict[str, Any]) -> dict[str, Any]:
    await ensure_explorer_columns(db)
    fields = row.get('fields') or row.get('fieldNames') or []
    if isinstance(fields, str):
        field_names = fields
    else:
        field_names = json.dumps(fields, ensure_ascii=False)
    parent_id = int(row.get('parentId') or row.get('parent_id') or 0)
    if parent_id:
        parent = await get_file(db, parent_id)
        if not parent or parent.get('itemType') != 'folder':
            raise ValueError('父级文件夹不存在')

    result = await db.execute(text('''
        INSERT INTO weather_file (
            item_type, parent_id, file_name, original_name, file_type, data_type, region_name, station_or_line,
            time_resolution, start_time, end_time, record_count, field_count, field_names,
            file_size, file_path, process_status, remark, create_by, create_time, update_time
        ) VALUES (
            :item_type, :parent_id, :file_name, :original_name, :file_type, :data_type, :region_name, :station_or_line,
            :time_resolution, :start_time, :end_time, :record_count, :field_count, :field_names,
            :file_size, :file_path, :process_status, :remark, :create_by, NOW(), NOW()
        )
    '''), {
        'item_type': row.get('itemType') or row.get('item_type') or 'file',
        'parent_id': parent_id,
        'file_name': row.get('name') or row.get('fileName') or row.get('originalName') or '',
        'original_name': row.get('originalName') or row.get('name') or '',
        'file_type': row.get('fileType') or 'excel',
        'data_type': row.get('dataType') or 'station_observation',
        'region_name': row.get('region') or row.get('regionName') or '',
        'station_or_line': row.get('stationOrLine') or row.get('station_or_line') or '',
        'time_resolution': row.get('timeResolution') or '',
        'start_time': row.get('startTime') or None,
        'end_time': row.get('endTime') or None,
        'record_count': int(row.get('recordCount') or 0),
        'field_count': int(row.get('fieldCount') or 0),
        'field_names': field_names,
        'file_size': int(row.get('fileSize') or 0),
        'file_path': row.get('filePath') or '',
        'process_status': row.get('status') or row.get('processStatus') or 'uploaded',
        'remark': row.get('remark') or '',
        'create_by': row.get('createBy') or '',
    })
    await db.commit()
    new_id = result.lastrowid
    saved = await get_file(db, new_id)
    return saved or {'id': new_id, **row}


async def update_file(db: AsyncSession, file_id: str | int, **kwargs: Any) -> dict[str, Any] | None:
    await ensure_explorer_columns(db)
    mapping = {
        'itemType': 'item_type',
        'item_type': 'item_type',
        'parentId': 'parent_id',
        'parent_id': 'parent_id',
        'name': 'file_name',
        'fileName': 'file_name',
        'originalName': 'original_name',
        'fileType': 'file_type',
        'dataType': 'data_type',
        'region': 'region_name',
        'regionName': 'region_name',
        'stationOrLine': 'station_or_line',
        'timeResolution': 'time_resolution',
        'startTime': 'start_time',
        'endTime': 'end_time',
        'recordCount': 'record_count',
        'fieldCount': 'field_count',
        'fields': 'field_names',
        'fileSize': 'file_size',
        'filePath': 'file_path',
        'status': 'process_status',
        'processStatus': 'process_status',
        'remark': 'remark',
    }
    sets: list[str] = []
    params: dict[str, Any] = {'id': int(file_id)}
    for key, col in mapping.items():
        if key in kwargs:
            value = kwargs[key]
            if key == 'fields' and isinstance(value, list):
                value = json.dumps(value, ensure_ascii=False)
            params[col] = value
            sets.append(f'{col} = :{col}')
    if not sets:
        return await get_file(db, file_id)
    sets.append('update_time = NOW()')
    await db.execute(text(f'UPDATE weather_file SET {", ".join(sets)} WHERE id = :id'), params)
    await db.commit()
    return await get_file(db, file_id)


async def create_folder(db: AsyncSession, name: str, parent_id: str | int = 0, remark: str = '') -> dict[str, Any]:
    clean_name = str(name or '').strip()
    if not clean_name:
        raise ValueError('文件夹名称不能为空')
    parent_id_int = int(parent_id or 0)
    if parent_id_int:
        parent = await get_file(db, parent_id_int)
        if not parent or parent.get('itemType') != 'folder':
            raise ValueError('父级文件夹不存在')
    return await save_file(db, {
        'name': clean_name,
        'originalName': clean_name,
        'itemType': 'folder',
        'parentId': parent_id_int,
        'fileType': 'folder',
        'dataType': 'folder',
        'status': 'finished',
        'remark': remark,
    })


async def _descendant_ids(db: AsyncSession, root_id: int) -> list[int]:
    await ensure_explorer_columns(db)
    descendants: list[int] = []
    pending = [root_id]
    seen = {root_id}
    while pending:
        current = pending.pop(0)
        result = await db.execute(text('SELECT id FROM weather_file WHERE parent_id = :parent_id'), {'parent_id': current})
        child_ids = [int(row._mapping['id']) for row in result.fetchall()]
        for child_id in child_ids:
            if child_id in seen:
                continue
            seen.add(child_id)
            descendants.append(child_id)
            pending.append(child_id)
    return descendants


async def move_item(db: AsyncSession, item_id: str | int, target_parent_id: str | int = 0) -> dict[str, Any] | None:
    item = await get_file(db, item_id)
    if not item:
        return None
    item_id_int = int(item_id)
    parent_id = int(target_parent_id or 0)
    if parent_id == item_id_int:
        raise ValueError('不能移动到自身目录')
    if parent_id:
        target = await get_file(db, parent_id)
        if not target or target.get('itemType') != 'folder':
            raise ValueError('目标文件夹不存在')
    if item.get('itemType') == 'folder' and parent_id in await _descendant_ids(db, item_id_int):
        raise ValueError('不能移动到自己的子目录')
    return await update_file(db, item_id_int, parentId=parent_id)


async def _raw_item(db: AsyncSession, item_id: int) -> dict[str, Any] | None:
    await ensure_explorer_columns(db)
    result = await db.execute(text('''
        SELECT item_type, parent_id, file_name, original_name, file_type, data_type, region_name, station_or_line,
               time_resolution, start_time, end_time, record_count, field_count, field_names,
               file_size, file_path, process_status, remark, create_by
        FROM weather_file
        WHERE id = :id
        LIMIT 1
    '''), {'id': item_id})
    row = result.fetchone()
    return dict(row._mapping) if row else None


def _copied_name(name: str) -> str:
    text_name = str(name or '未命名')
    suffix = ' - 副本'
    if text_name.endswith(suffix):
        return f'{text_name} 2'
    return f'{text_name}{suffix}'


def _copy_physical_file(file_path: str | None) -> tuple[str, int]:
    if not file_path:
        return '', 0
    source = Path(file_path)
    if not source.is_absolute():
        source = Path.cwd() / source
    if not source.exists() or not source.is_file():
        return file_path, 0
    target = UPLOAD_DIR / f'{datetime.now().strftime("%Y%m%d%H%M%S_%f")}_{source.stem}_copy{source.suffix}'
    shutil.copy2(source, target)
    return str(target).replace('\\', '/'), target.stat().st_size


async def _copy_single_item(
    db: AsyncSession,
    source_id: int,
    target_parent_id: int,
    copied_name: str | None = None,
    keep_original_name: bool = False,
) -> dict[str, Any]:
    source = await _raw_item(db, source_id)
    if not source:
        raise ValueError('要复制的文件不存在')
    item_type = source.get('item_type') or 'file'
    source_name = source.get('file_name') or source.get('original_name') or ''
    file_path = source.get('file_path') or ''
    file_size = int(source.get('file_size') or 0)
    if item_type != 'folder':
        file_path, copied_size = _copy_physical_file(file_path)
        if copied_size:
            file_size = copied_size
    return await save_file(db, {
        'itemType': item_type,
        'parentId': target_parent_id,
        'name': copied_name or (source_name if keep_original_name else _copied_name(source_name)),
        'originalName': source.get('original_name') or source.get('file_name') or '',
        'fileType': source.get('file_type') or ('folder' if item_type == 'folder' else 'excel'),
        'dataType': source.get('data_type') or ('folder' if item_type == 'folder' else 'station_observation'),
        'region': source.get('region_name') or '',
        'stationOrLine': source.get('station_or_line') or '',
        'timeResolution': source.get('time_resolution') or '',
        'startTime': source.get('start_time') or None,
        'endTime': source.get('end_time') or None,
        'recordCount': int(source.get('record_count') or 0),
        'fieldCount': int(source.get('field_count') or 0),
        'fields': source.get('field_names') or '',
        'fileSize': file_size,
        'filePath': file_path,
        'status': source.get('process_status') or 'pending',
        'remark': source.get('remark') or '',
        'createBy': source.get('create_by') or '',
    })


async def copy_item(db: AsyncSession, item_id: str | int, target_parent_id: str | int = 0) -> dict[str, Any]:
    item = await get_file(db, item_id)
    if not item:
        raise ValueError('要复制的文件不存在')
    parent_id = int(target_parent_id or 0)
    if parent_id:
        target = await get_file(db, parent_id)
        if not target or target.get('itemType') != 'folder':
            raise ValueError('目标文件夹不存在')
    root_copy = await _copy_single_item(db, int(item_id), parent_id)
    if item.get('itemType') == 'folder':
        source_to_copy = {int(item_id): int(root_copy['id'])}
        pending = [int(item_id)]
        while pending:
            current_source = pending.pop(0)
            children = await db.execute(text('SELECT id FROM weather_file WHERE parent_id = :parent_id ORDER BY id ASC'), {'parent_id': current_source})
            for row in children.fetchall():
                child_source_id = int(row._mapping['id'])
                child_copy = await _copy_single_item(db, child_source_id, source_to_copy[current_source], None, True)
                source_to_copy[child_source_id] = int(child_copy['id'])
                if child_copy.get('itemType') == 'folder':
                    pending.append(child_source_id)
    return root_copy


async def delete_file(db: AsyncSession, file_id: str | int) -> bool:
    await ensure_explorer_columns(db)
    ids = [int(file_id), *await _descendant_ids(db, int(file_id))]
    deleted = 0
    for current_id in reversed(ids):
        result = await db.execute(text('DELETE FROM weather_file WHERE id = :id'), {'id': current_id})
        deleted += int(result.rowcount or 0)
    await db.commit()
    return bool(deleted)
