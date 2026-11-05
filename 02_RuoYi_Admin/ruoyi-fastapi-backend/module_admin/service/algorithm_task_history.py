"""Persist task state changes independently from the latest task snapshot."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

HISTORY_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS algorithm_task_history (
        id bigint NOT NULL AUTO_INCREMENT PRIMARY KEY,
        task_code varchar(128) NOT NULL,
        task_status varchar(32) NOT NULL,
        progress int NOT NULL DEFAULT 0,
        message text,
        error_message text,
        event_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_task_history (task_code, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
STATE_FIELDS = ('status', 'progress', 'message', 'error')


async def ensure_history_table(db: AsyncSession) -> None:
    # Existing installations only require read/write access after applying the migration.
    try:
        await db.execute(text('SELECT 1 FROM algorithm_task_history LIMIT 0'))
        return
    except ProgrammingError as exc:
        if not getattr(exc.orig, 'args', ()) or exc.orig.args[0] != 1146:
            raise
        await db.rollback()
    # Run before task mutations: MySQL DDL may implicitly commit a transaction.
    await db.execute(text(HISTORY_TABLE_SQL))
    await db.commit()


def state_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return any(before.get(key) != after.get(key) for key in STATE_FIELDS)


async def append_task_history(db: AsyncSession, task: dict[str, Any]) -> None:
    """Caller commits this insert together with the task snapshot."""
    await db.execute(text("""
        INSERT INTO algorithm_task_history (task_code, task_status, progress, message, error_message)
        VALUES (:task_code, :task_status, :progress, :message, :error_message)
    """), {
        'task_code': task['taskCode'],
        'task_status': task.get('status') or 'created',
        'progress': int(task.get('progress') or 0),
        'message': task.get('message') or '',
        'error_message': task.get('error'),
    })


async def list_task_history(
    db: AsyncSession, task_code: str, page_num: int = 1, page_size: int = 20,
) -> dict[str, Any]:
    await ensure_history_table(db)
    params = {'task_code': task_code, 'limit': page_size, 'offset': (page_num - 1) * page_size}
    count = await db.execute(text(
        'SELECT COUNT(*) FROM algorithm_task_history WHERE task_code = :task_code'
    ), {'task_code': task_code})
    total = int(count.scalar() or 0)
    result = await db.execute(text("""
        SELECT id, task_status, progress, message, error_message, event_time
        FROM algorithm_task_history
        WHERE task_code = :task_code
        ORDER BY id DESC
        LIMIT :limit OFFSET :offset
    """), params)
    rows = []
    for row in result.fetchall():
        values = row._mapping
        rows.append({
            'id': values['id'],
            'status': values['task_status'],
            'progress': values['progress'],
            'message': values['message'] or '',
            'error': values['error_message'] or '',
            'eventTime': str(values['event_time']),
        })
    return {'rows': rows, 'total': total}
