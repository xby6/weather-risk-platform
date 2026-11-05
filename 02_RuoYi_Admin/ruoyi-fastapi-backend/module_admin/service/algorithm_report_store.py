"""Durable report snapshots, configuration and a database-backed work queue."""
from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from module_admin.service.algorithm_report_prompt import TEMPLATE_VERSION, safe_data

REPORT_DIR = Path('vf_admin/algorithm_reports')
RESULT_DIR = Path('vf_admin/algorithm_results')
MAX_FILE_BYTES = 128 * 1024 * 1024
SCHEMA_SQL = [
    '''CREATE TABLE IF NOT EXISTS algorithm_report_config (
        id int NOT NULL PRIMARY KEY,
        model_id bigint NULL,
        auto_enabled tinyint NOT NULL DEFAULT 0,
        auto_since varchar(32) NOT NULL DEFAULT '',
        instructions text,
        update_time datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
    '''CREATE TABLE IF NOT EXISTS algorithm_report (
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
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
]


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


async def ensure_report_tables(db: AsyncSession) -> None:
    for name, ddl in zip(('algorithm_report_config', 'algorithm_report'), SCHEMA_SQL):
        try:
            await db.execute(text(f'SELECT 1 FROM {name} LIMIT 0'))
        except ProgrammingError as exc:
            if not getattr(exc.orig, 'args', ()) or exc.orig.args[0] != 1146:
                raise
            await db.rollback()
            await db.execute(text(ddl))
            await db.commit()


async def get_config(db: AsyncSession) -> dict[str, Any]:
    await ensure_report_tables(db)
    result = await db.execute(text('SELECT * FROM algorithm_report_config WHERE id = 1'))
    row = result.fetchone()
    if not row:
        return {'modelId': None, 'autoEnabled': False, 'autoSince': '', 'instructions': ''}
    values = row._mapping
    return {'modelId': values['model_id'], 'autoEnabled': bool(values['auto_enabled']),
            'autoSince': values['auto_since'], 'instructions': values['instructions'] or ''}


async def save_config(db: AsyncSession, model_id: int, auto_enabled: bool, instructions: str) -> dict[str, Any]:
    current = await get_config(db)
    since = current['autoSince'] if current['autoEnabled'] and auto_enabled else ''
    if auto_enabled and not since:
        since = datetime.now().isoformat(timespec='microseconds')
    await db.execute(text('''
        INSERT INTO algorithm_report_config (id, model_id, auto_enabled, auto_since, instructions)
        VALUES (1, :model_id, :auto_enabled, :auto_since, :instructions)
        ON DUPLICATE KEY UPDATE model_id = VALUES(model_id), auto_enabled = VALUES(auto_enabled),
            auto_since = VALUES(auto_since), instructions = VALUES(instructions), update_time = NOW()
    '''), {'model_id': model_id, 'auto_enabled': int(auto_enabled), 'auto_since': since, 'instructions': instructions})
    await db.commit()
    return await get_config(db)


async def get_enabled_model(db: AsyncSession, model_id: int) -> dict[str, Any]:
    result = await db.execute(text('''SELECT model_id, model_code, model_name, provider, api_key,
        base_url, temperature, max_tokens, status FROM ai_models WHERE model_id = :id'''), {'id': model_id})
    row = result.fetchone()
    if not row or row._mapping['status'] != '0':
        raise ValueError('默认LLM不存在或已停用，请在报告设置中选择启用的模型')
    return dict(row._mapping)


def model_info(model: dict[str, Any]) -> dict[str, Any]:
    return {key: model.get(key) for key in ('model_id', 'provider', 'model_code', 'model_name', 'temperature', 'max_tokens')}


def snapshot_result_file(source_path: str, report_id: str) -> str:
    if not source_path:
        return ''
    source = Path(source_path).resolve()
    if not source.is_relative_to(RESULT_DIR.resolve()) or not source.is_file():
        return ''
    if source.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('结果文件超过128MB，首版暂不支持生成文件分析报告')
    directory = REPORT_DIR / report_id
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / ('source' + source.suffix.lower())
    shutil.copy2(source, destination)
    return str(destination.resolve())


async def enqueue_report(db: AsyncSession, task_code: str, *, force: bool = False) -> dict[str, Any]:
    import asyncio
    from module_admin.service.algorithm_model_store import get_model_by_algorithm_id
    from module_admin.service.algorithm_task_store import get_task

    config = await get_config(db)
    if not config['modelId']:
        raise ValueError('请先在报告设置中选择默认LLM')
    model = await get_enabled_model(db, config['modelId'])
    task = await get_task(db, task_code, for_update=True)
    if not task or task['status'] != 'success' or task['result'] in (None, {}, []):
        raise ValueError('仅能为成功且已有结果的任务生成报告')
    raw = task.get('rawInputParams') or {}
    source_key = hashlib.sha256(dumps({'taskCode': task_code, 'runId': raw.get('reportRunId'),
                                     'result': task['result'], 'params': task['params']}).encode()).hexdigest()
    existing = await db.execute(text('SELECT * FROM algorithm_report WHERE source_key = :key ORDER BY version DESC LIMIT 1'), {'key': source_key})
    row = existing.fetchone()
    if row and (not force or row._mapping['report_status'] in {'queued', 'running'}):
        await db.commit()
        return report_vo(dict(row._mapping))
    algorithm = await get_model_by_algorithm_id(db, task['algorithmId'], server_id=task.get('serverId'), server_url=task.get('serverUrl'))
    task_info = {key: task.get(key) for key in ('taskCode', 'taskName', 'algorithmId', 'algorithmName', 'taskType',
                'region', 'lineCode', 'fileId', 'forecastHours', 'startTime', 'endTime', 'dataSource', 'params')}
    task_info['runId'] = raw.get('reportRunId') or 'legacy-result'
    task_info['runStartedAt'] = raw.get('reportRunStartedAt') or ''
    snapshot = {'task': safe_data(task_info), 'algorithm': safe_data(algorithm or {}), 'result': task['result']}
    report_id = str(uuid.uuid4())
    snapshot_path = await asyncio.to_thread(snapshot_result_file, task.get('resultPath') or '', report_id)
    version = int(row._mapping['version']) + 1 if row else 1
    await db.execute(text('''INSERT INTO algorithm_report
        (id, task_code, source_key, version, title, model_id, model_info, snapshot_json, snapshot_path, instructions)
        VALUES (:id, :task_code, :source_key, :version, :title, :model_id, :model_info, :snapshot_json, :snapshot_path, :instructions)
    '''), {'id': report_id, 'task_code': task_code, 'source_key': source_key, 'version': version,
           'title': (task['taskName'] + ' · 结果分析报告')[:255], 'model_id': config['modelId'],
           'model_info': dumps(model_info(model)), 'snapshot_json': dumps(snapshot), 'snapshot_path': snapshot_path,
           'instructions': config['instructions']})
    await db.commit()
    return await get_report(db, report_id)


async def enqueue_auto_report(db: AsyncSession, task: dict[str, Any]) -> None:
    raw = task.get('rawInputParams') or {}
    if not raw.get('reportRunId') or task.get('status') != 'success':
        return
    config = await get_config(db)
    if config['autoEnabled'] and config['modelId'] and raw.get('reportRunStartedAt', '') >= config['autoSince']:
        await enqueue_report(db, task['taskCode'])


def report_vo(values: dict[str, Any], *, detail: bool = True) -> dict[str, Any]:
    output = {
        'id': values['id'], 'taskCode': values['task_code'], 'version': values['version'], 'title': values['title'],
        'status': values['report_status'], 'modelInfo': json.loads(values['model_info']),
        'attempts': values['attempts'], 'error': values.get('error_message') or '',
        'createTime': str(values['create_time']), 'updateTime': str(values['update_time']), 'templateVersion': TEMPLATE_VERSION,
    }
    if detail:
        output.update({'content': values.get('content') or '', 'prompt': values.get('prompt') or '',
                       'analysis': json.loads(values['analysis_json']) if values.get('analysis_json') else None,
                       'facts': json.loads(values['facts_json']) if values.get('facts_json') else None})
    return output


async def get_report(db: AsyncSession, report_id: str) -> dict[str, Any] | None:
    result = await db.execute(text('SELECT * FROM algorithm_report WHERE id = :id'), {'id': report_id})
    row = result.fetchone()
    return report_vo(dict(row._mapping)) if row else None


async def list_reports(db: AsyncSession, task_code: str) -> list[dict[str, Any]]:
    await ensure_report_tables(db)
    result = await db.execute(text('''SELECT id, task_code, version, title, report_status, model_info,
        attempts, error_message, create_time, update_time FROM algorithm_report
        WHERE task_code = :code ORDER BY create_time DESC, version DESC'''), {'code': task_code})
    return [report_vo(dict(row._mapping), detail=False) for row in result.fetchall()]


async def retry_report(db: AsyncSession, report_id: str) -> bool:
    result = await db.execute(text('''UPDATE algorithm_report SET report_status = 'queued', attempts = 0,
        error_message = NULL, lease_token = NULL, lease_until = NULL, next_attempt_at = :now, update_time = :now
        WHERE id = :id AND report_status = 'failed' '''), {'id': report_id, 'now': datetime.now()})
    await db.commit()
    return bool(result.rowcount)


async def claim_report(db: AsyncSession) -> dict[str, Any] | None:
    now = datetime.now()
    await db.execute(text('''UPDATE algorithm_report SET report_status = 'failed',
        error_message = '后台执行中断且重试次数已用尽，请手动重试', update_time = :now
        WHERE report_status = 'running' AND lease_until < :now AND attempts >= 3'''), {'now': now})
    candidates = await db.execute(text('''SELECT id FROM algorithm_report WHERE attempts < 3 AND
        ((report_status = 'queued' AND next_attempt_at <= :now) OR (report_status = 'running' AND lease_until < :now))
        ORDER BY create_time LIMIT 10'''), {'now': now})
    for row in candidates.fetchall():
        token = str(uuid.uuid4())
        claimed = await db.execute(text('''UPDATE algorithm_report SET report_status = 'running',
            lease_token = :token, lease_until = :until, attempts = attempts + 1, update_time = :now
            WHERE id = :id AND attempts < 3 AND ((report_status = 'queued' AND next_attempt_at <= :now)
                OR (report_status = 'running' AND lease_until < :now))'''),
            {'token': token, 'until': now + timedelta(minutes=5), 'now': now, 'id': row._mapping['id']})
        if claimed.rowcount:
            await db.commit()
            result = await db.execute(text('SELECT * FROM algorithm_report WHERE id = :id'), {'id': row._mapping['id']})
            return dict(result.fetchone()._mapping)
    await db.commit()
    return None
