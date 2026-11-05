from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from module_admin.service.algorithm_task_history import (
    append_task_history,
    ensure_history_table,
    state_changed,
)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _json_loads(value: Any, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _normalize_params(value: Any) -> dict[str, Any]:
    params = value if isinstance(value, dict) else {}
    nested = params.get("params")
    if isinstance(nested, dict):
        params = {**params, **nested}
    params = {key: item for key, item in params.items() if key not in {'reportRunId', 'reportRunStartedAt'}}
    return params


def _row_to_vo(row: Any) -> dict[str, Any]:
    m = row._mapping if hasattr(row, "_mapping") else row
    raw_input = _json_loads(m.get("input_params"), {}) or {}
    params = _normalize_params(raw_input)
    result = _json_loads(m.get("result_json"), None)
    return {
        "id": m.get("id"),
        "taskCode": m.get("task_code") or "",
        "taskName": m.get("task_name") or "",
        "serverId": m.get("server_id"),
        "serverUrl": m.get("server_url") or "",
        "algorithmId": m.get("algorithm_id") or "",
        "algorithmName": m.get("algorithm_name") or m.get("algorithm_id") or "",
        "taskType": m.get("task_type") or "",
        "priority": m.get("priority") or "normal",
        "region": m.get("region_name") or "",
        "lineCode": m.get("line_code") or "",
        "fileId": m.get("file_id"),
        "forecastHours": m.get("forecast_hours") or params.get("forecast_hours") or 24,
        "startTime": str(m.get("start_time") or ""),
        "endTime": str(m.get("end_time") or ""),
        "dataSource": raw_input.get("dataSource") or raw_input.get("data_source") or "",
        "params": params,
        "rawInputParams": raw_input,
        "status": m.get("task_status") or "created",
        "progress": m.get("progress") or 0,
        "message": m.get("message") or "",
        "result": result,
        "resultPath": m.get("result_path") or "",
        "error": m.get("error_message"),
        "remark": m.get("remark") or "",
        "createBy": m.get("create_by") or "",
        "createTime": str(m.get("create_time") or ""),
        "updateTime": str(m.get("update_time") or ""),
    }


async def list_tasks(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(text("""
        SELECT id, task_code, task_name, server_id, server_url, algorithm_id, algorithm_name,
               task_type, priority, region_name, line_code, file_id, forecast_hours, start_time,
               end_time, input_params, task_status, progress, message, result_json, result_path,
               error_message, remark, create_by, create_time, update_time
        FROM algorithm_task
        ORDER BY create_time DESC, id DESC
    """))
    return [_row_to_vo(row) for row in result.fetchall()]


async def get_task(db: AsyncSession, task_code: str, *, for_update: bool = False) -> dict[str, Any] | None:
    query = """
        SELECT id, task_code, task_name, server_id, server_url, algorithm_id, algorithm_name,
               task_type, priority, region_name, line_code, file_id, forecast_hours, start_time,
               end_time, input_params, task_status, progress, message, result_json, result_path,
               error_message, remark, create_by, create_time, update_time
        FROM algorithm_task
        WHERE task_code = :task_code
        LIMIT 1
    """
    if for_update:
        query += " FOR UPDATE"
    result = await db.execute(text(query), {"task_code": task_code})
    row = result.fetchone()
    return _row_to_vo(row) if row else None


async def save_task(db: AsyncSession, task: dict[str, Any]) -> dict[str, Any]:
    existing = await get_task(db, task.get("taskCode") or "")
    if existing:
        return await update_task(db, task.get("taskCode"), **task) or existing

    await ensure_history_table(db)

    raw_input = dict(task.get("rawInputParams") or {})
    raw_input["params"] = task.get("params") or {}
    if task.get("dataSource"):
        raw_input["dataSource"] = task.get("dataSource")

    await db.execute(text("""
        INSERT INTO algorithm_task (
            task_code, task_name, server_id, server_url, algorithm_id, algorithm_name, task_type,
            priority, region_name, line_code, file_id, forecast_hours, start_time, end_time,
            input_params, task_status, progress, message, result_json, result_path, error_message,
            remark, create_by, create_time, update_time
        ) VALUES (
            :task_code, :task_name, :server_id, :server_url, :algorithm_id, :algorithm_name, :task_type,
            :priority, :region_name, :line_code, :file_id, :forecast_hours, :start_time, :end_time,
            :input_params, :task_status, :progress, :message, :result_json, :result_path, :error_message,
            :remark, :create_by, NOW(), NOW()
        )
    """), {
        "task_code": task.get("taskCode"),
        "task_name": task.get("taskName") or "未命名算法任务",
        "server_id": task.get("serverId"),
        "server_url": task.get("serverUrl") or "",
        "algorithm_id": task.get("algorithmId") or "",
        "algorithm_name": task.get("algorithmName") or task.get("algorithmId") or "",
        "task_type": task.get("taskType") or "icing",
        "priority": task.get("priority") or "normal",
        "region_name": task.get("region") or task.get("regionName") or "",
        "line_code": task.get("lineCode") or "",
        "file_id": task.get("fileId"),
        "forecast_hours": int(task.get("forecastHours") or 24),
        "start_time": task.get("startTime") or None,
        "end_time": task.get("endTime") or None,
        "input_params": _json_dumps(raw_input),
        "task_status": task.get("status") or "created",
        "progress": int(task.get("progress") or 0),
        "message": task.get("message") or "任务已创建",
        "result_json": _json_dumps(task.get("result")) if task.get("result") is not None else None,
        "result_path": task.get("resultPath") or "",
        "error_message": task.get("error"),
        "remark": task.get("remark") or "",
        "create_by": task.get("createBy") or "",
    })
    await append_task_history(db, task)
    await db.commit()
    return await get_task(db, task.get("taskCode")) or task


async def update_task(db: AsyncSession, task_code: str, **kwargs: Any) -> dict[str, Any] | None:
    await ensure_history_table(db)
    current = await get_task(db, task_code, for_update=True)
    if not current:
        return None
    mapping = {
        "taskName": "task_name",
        "serverId": "server_id",
        "serverUrl": "server_url",
        "algorithmId": "algorithm_id",
        "algorithmName": "algorithm_name",
        "taskType": "task_type",
        "priority": "priority",
        "region": "region_name",
        "regionName": "region_name",
        "lineCode": "line_code",
        "fileId": "file_id",
        "forecastHours": "forecast_hours",
        "startTime": "start_time",
        "endTime": "end_time",
        "status": "task_status",
        "progress": "progress",
        "message": "message",
        "resultPath": "result_path",
        "error": "error_message",
        "remark": "remark",
    }
    sets: list[str] = []
    params: dict[str, Any] = {"task_code": task_code}

    for key, col in mapping.items():
        if key in kwargs:
            value = kwargs[key]
            if key in {"startTime", "endTime"} and value == "":
                value = None
            params[col] = value
            sets.append(f"{col} = :{col}")

    if "params" in kwargs or "rawInputParams" in kwargs or "dataSource" in kwargs:
        raw_input = current.get("rawInputParams") if current else {}
        if not isinstance(raw_input, dict):
            raw_input = {}
        if "params" in kwargs:
            raw_input["params"] = kwargs.get("params") or {}
        if "rawInputParams" in kwargs and isinstance(kwargs.get("rawInputParams"), dict):
            raw_input.update(kwargs.get("rawInputParams"))
        if "dataSource" in kwargs:
            raw_input["dataSource"] = kwargs.get("dataSource") or ""
        params["input_params"] = _json_dumps(raw_input)
        sets.append("input_params = :input_params")

    if "result" in kwargs:
        params["result_json"] = _json_dumps(kwargs.get("result"))
        sets.append("result_json = :result_json")

    if not sets:
        return await get_task(db, task_code)

    sets.append("update_time = NOW()")
    await db.execute(text(f"UPDATE algorithm_task SET {', '.join(sets)} WHERE task_code = :task_code"), params)
    updated = {**current, **kwargs, "taskCode": task_code}
    if state_changed(current, updated):
        await append_task_history(db, updated)
    await db.commit()
    return await get_task(db, task_code)


async def delete_task(db: AsyncSession, task_code: str) -> bool:
    await ensure_history_table(db)
    result = await db.execute(text("DELETE FROM algorithm_task WHERE task_code = :task_code"), {"task_code": task_code})
    await db.execute(text("DELETE FROM algorithm_task_history WHERE task_code = :task_code"), {"task_code": task_code})
    await db.commit()
    return bool(result.rowcount)


async def claim_task_run(db: AsyncSession, task_code: str) -> bool:
    """Serialize submissions for a task before contacting the remote algorithm service."""
    await ensure_history_table(db)
    task = await get_task(db, task_code, for_update=True)
    if not task or task.get("status") in {"submitted", "queued", "running"}:
        await db.rollback()
        return False
    await update_task(
        db, task_code, status="submitted", progress=0, message="正在提交到 algorithm-server",
        error=None, result=None, resultPath="",
        rawInputParams={"reportRunId": str(uuid.uuid4()), "reportRunStartedAt": datetime.now().isoformat(timespec='microseconds')},
    )
    return True


def _coalesce_params(payload: dict[str, Any]) -> dict[str, Any]:
    source = dict(payload.get("params") or {})
    aliases = {
        "temperature": ["temperature"],
        "humidity": ["humidity"],
        "wind_speed": ["wind_speed", "windSpeed"],
        "wind_direction": ["wind_direction", "windDirection"],
        "precipitation": ["precipitation"],
        "history_icing_thickness": ["history_icing_thickness", "historyIcingThickness", "icingThickness", "icing_thickness"],
        "forecast_hours": ["forecast_hours", "forecastHours"],
    }
    for target, keys in aliases.items():
        if source.get(target) not in (None, ""):
            continue
        for key in keys:
            value = payload.get(key)
            if value in (None, ""):
                value = source.get(key)
            if value not in (None, ""):
                source[target] = value
                break
    return source


async def create_task(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    task_code = payload.get("taskCode") or f"TASK_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    algorithm_id = payload.get("algorithmId") or payload.get("algorithm") or payload.get("modelId") or ""
    forecast_hours = int(payload.get("forecastHours") or payload.get("forecast_hours") or 24)
    params = _coalesce_params({**payload, "forecastHours": forecast_hours})
    params["forecast_hours"] = forecast_hours

    task = {
        "taskCode": task_code,
        "taskName": payload.get("taskName") or "未命名算法任务",
        "taskType": payload.get("taskType") or "icing",
        "serverId": payload.get("serverId"),
        "serverUrl": payload.get("serverUrl") or payload.get("server_url") or "",
        "algorithmId": algorithm_id,
        "algorithmName": payload.get("algorithmName") or algorithm_id,
        "region": payload.get("region") or payload.get("regionName") or "",
        "lineCode": payload.get("lineCode") or "",
        "fileId": payload.get("fileId"),
        "forecastHours": forecast_hours,
        "priority": payload.get("priority") or "normal",
        "startTime": payload.get("startTime") or "",
        "endTime": payload.get("endTime") or "",
        "dataSource": payload.get("dataSource") or payload.get("data_source") or "",
        "params": params,
        "remark": payload.get("remark") or "",
        "status": "created",
        "progress": 0,
        "message": "任务已创建",
        "result": None,
        "error": None,
        "createTime": _now(),
        "updateTime": _now(),
    }
    return await save_task(db, task)
