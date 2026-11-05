from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


MODEL_UPLOAD_DIR = Path("vf_admin/algorithm_models")


def _json_dumps(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _row_to_vo(row: Any) -> dict[str, Any]:
    m = row._mapping if hasattr(row, "_mapping") else row
    return {
        "id": str(m.get("id")),
        "serverId": str(m.get("server_id") or ""),
        "serverUrl": m.get("server_url") or "",
        "algorithm_id": m.get("algorithm_id") or "",
        "algorithmId": m.get("algorithm_id") or "",
        "model_id": m.get("algorithm_id") or "",
        "modelId": m.get("algorithm_id") or "",
        "algorithm_name": m.get("algorithm_name") or "",
        "algorithmName": m.get("algorithm_name") or "",
        "algorithm_type": m.get("algorithm_type") or "",
        "algorithmType": m.get("algorithm_type") or "",
        "algorithm_version": m.get("algorithm_version") or "",
        "version": m.get("algorithm_version") or "",
        "runApi": m.get("run_api") or "",
        "run_api": m.get("run_api") or "",
        "inputSchema": m.get("input_schema") or "",
        "input_schema": m.get("input_schema") or "",
        "outputSchema": m.get("output_schema") or "",
        "output_schema": m.get("output_schema") or "",
        "status": m.get("status") or "enabled",
        "description": m.get("remark") or "",
        "remark": m.get("remark") or "",
        "createTime": str(m.get("create_time") or ""),
        "updateTime": str(m.get("update_time") or ""),
    }


async def _find_server_id(db: AsyncSession, payload: dict[str, Any]) -> int | None:
    server_id = payload.get("serverId") or payload.get("server_id")
    if server_id not in (None, ""):
        try:
            return int(server_id)
        except Exception:
            pass

    server_url = str(payload.get("serverUrl") or payload.get("server_url") or payload.get("url") or "").rstrip("/")
    if server_url:
        result = await db.execute(
            text("SELECT id FROM algorithm_server WHERE server_url = :server_url LIMIT 1"),
            {"server_url": server_url},
        )
        row = result.fetchone()
        if row:
            return int(row._mapping.get("id"))
    return None


async def _ensure_server(db: AsyncSession, server_url: str) -> int | None:
    server_url = str(server_url or "").rstrip("/")
    if not server_url:
        return None

    result = await db.execute(
        text("SELECT id FROM algorithm_server WHERE server_url = :server_url LIMIT 1"),
        {"server_url": server_url},
    )
    row = result.fetchone()
    if row:
        return int(row._mapping.get("id"))

    inserted = await db.execute(text("""
        INSERT INTO algorithm_server (server_name, server_url, status, remark, create_time, update_time)
        VALUES (:server_name, :server_url, 'unknown', 'Synced from algorithm-server', NOW(), NOW())
    """), {"server_name": server_url, "server_url": server_url})
    await db.commit()
    return int(inserted.lastrowid)


async def list_models(
    db: AsyncSession,
    server_id: str | int | None = None,
    server_url: str | None = None,
) -> list[dict[str, Any]]:
    where: list[str] = ["COALESCE(m.status, 'enabled') <> 'deleted'"]
    params: dict[str, Any] = {}
    if server_id not in (None, ""):
        where.append("m.server_id = :server_id")
        params["server_id"] = int(server_id)
    if server_url:
        where.append("s.server_url = :server_url")
        params["server_url"] = str(server_url).rstrip("/")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    result = await db.execute(text(f"""
        SELECT m.id, m.server_id, s.server_url, m.algorithm_id, m.algorithm_name, m.algorithm_type,
               m.algorithm_version, m.run_api, m.input_schema, m.output_schema, m.status,
               m.remark, m.create_time, m.update_time
        FROM algorithm_model m
        LEFT JOIN algorithm_server s ON m.server_id = s.id
        {where_sql}
        ORDER BY m.update_time DESC, m.id DESC
    """), params)
    return [_row_to_vo(row) for row in result.fetchall()]


async def get_model(db: AsyncSession, model_id: str | int) -> dict[str, Any] | None:
    result = await db.execute(text("""
        SELECT m.id, m.server_id, s.server_url, m.algorithm_id, m.algorithm_name, m.algorithm_type,
               m.algorithm_version, m.run_api, m.input_schema, m.output_schema, m.status,
               m.remark, m.create_time, m.update_time
        FROM algorithm_model m
        LEFT JOIN algorithm_server s ON m.server_id = s.id
        WHERE m.id = :id
        LIMIT 1
    """), {"id": int(model_id)})
    row = result.fetchone()
    return _row_to_vo(row) if row else None


async def get_model_by_algorithm_id(
    db: AsyncSession,
    algorithm_id: str,
    server_id: str | int | None = None,
    server_url: str | None = None,
) -> dict[str, Any] | None:
    rows = await list_models(db, server_id=server_id, server_url=server_url)
    for row in rows:
        if str(row.get("algorithmId")) == str(algorithm_id):
            return row
    return None


async def create_model(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    algorithm_id = str(payload.get("algorithmId") or payload.get("algorithm_id") or payload.get("modelId") or "").strip()
    algorithm_name = str(payload.get("algorithmName") or payload.get("algorithm_name") or algorithm_id).strip()
    if not algorithm_id:
        raise ValueError("算法编号不能为空")
    if not algorithm_name:
        raise ValueError("算法名称不能为空")

    server_id = await _find_server_id(db, payload)
    params = {
        "server_id": server_id,
        "algorithm_id": algorithm_id,
        "algorithm_name": algorithm_name,
        "algorithm_type": payload.get("algorithmType") or payload.get("algorithm_type") or payload.get("type") or "icing",
        "algorithm_version": payload.get("version") or payload.get("algorithmVersion") or payload.get("algorithm_version") or "v1.0",
        "run_api": payload.get("runApi") or payload.get("run_api") or "/api/tasks/run",
        "input_schema": _json_dumps(payload.get("inputSchema") or payload.get("input_schema")),
        "output_schema": _json_dumps(payload.get("outputSchema") or payload.get("output_schema")),
        "status": payload.get("status") or "enabled",
        "remark": payload.get("description") or payload.get("remark") or "",
    }

    if server_id is not None:
        result = await db.execute(text("""
            SELECT id, status FROM algorithm_model
            WHERE server_id = :server_id AND algorithm_id = :algorithm_id
            LIMIT 1
        """), {"server_id": server_id, "algorithm_id": algorithm_id})
    else:
        result = await db.execute(text("""
            SELECT id, status FROM algorithm_model
            WHERE server_id IS NULL AND algorithm_id = :algorithm_id
            LIMIT 1
        """), {"algorithm_id": algorithm_id})
    existing = result.fetchone()

    if existing:
        model_id = int(existing._mapping.get("id"))
        existing_status = str(existing._mapping.get("status") or "")
        if existing_status in {"disabled", "deleted"} and payload.get("preserveLocalStatus"):
            return await get_model(db, model_id) or {"id": str(model_id), **payload, "status": existing_status}
        params["id"] = model_id
        await db.execute(text("""
            UPDATE algorithm_model
            SET server_id = :server_id,
                algorithm_name = :algorithm_name,
                algorithm_type = :algorithm_type,
                algorithm_version = :algorithm_version,
                run_api = :run_api,
                input_schema = :input_schema,
                output_schema = :output_schema,
                status = :status,
                remark = :remark,
                update_time = NOW()
            WHERE id = :id
        """), params)
    else:
        inserted = await db.execute(text("""
            INSERT INTO algorithm_model
            (server_id, algorithm_id, algorithm_name, algorithm_type, algorithm_version,
             run_api, input_schema, output_schema, status, remark, create_time, update_time)
            VALUES
            (:server_id, :algorithm_id, :algorithm_name, :algorithm_type, :algorithm_version,
             :run_api, :input_schema, :output_schema, :status, :remark, NOW(), NOW())
        """), params)
        model_id = int(inserted.lastrowid)

    await db.commit()
    await _refresh_server_model_count(db, server_id)
    model = await get_model(db, model_id)
    return model or {"id": str(model_id), **payload}


async def update_model_status(db: AsyncSession, model_id: str | int, status: str) -> dict[str, Any] | None:
    model = await get_model(db, model_id)
    if not model or model.get("status") == "deleted":
        return None
    await db.execute(
        text("UPDATE algorithm_model SET status = :status, update_time = NOW() WHERE id = :id"),
        {"id": int(model_id), "status": status or "enabled"},
    )
    await db.commit()
    return await get_model(db, model_id)


async def delete_model(db: AsyncSession, model_id: str | int) -> bool:
    model = await get_model(db, model_id)
    if not model:
        return False
    server_id = model.get("serverId") or None
    result = await db.execute(
        text("UPDATE algorithm_model SET status = 'deleted', update_time = NOW() WHERE id = :id"),
        {"id": int(model_id)},
    )
    await db.commit()
    try:
        await _refresh_server_model_count(db, int(server_id) if server_id else None)
    except Exception:
        pass
    return bool(result.rowcount)


async def upload_model_file(db: AsyncSession, file: UploadFile, payload: dict[str, Any]) -> dict[str, Any]:
    MODEL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original = file.filename or "model.bin"
    safe_name = original.replace("..", "_").replace("/", "_").replace("\\", "_")
    algorithm_id = payload.get("algorithmId") or payload.get("algorithm_id") or Path(safe_name).stem
    target = MODEL_UPLOAD_DIR / f"{algorithm_id}_{safe_name}"
    content = await file.read()
    target.write_bytes(content)

    remark_parts = [f"local_model_path={target.as_posix()}"]
    if payload.get("remoteModelId"):
        remark_parts.append(f"remote_model_id={payload.get('remoteModelId')}")
    if payload.get("remark") or payload.get("description"):
        remark_parts.append(str(payload.get("remark") or payload.get("description")))

    local_payload = {
        **payload,
        "remark": "; ".join(remark_parts),
        "runApi": payload.get("runApi") or "/api/tasks/run",
    }
    return await create_model(db, local_payload)


async def sync_remote_algorithms(
    db: AsyncSession,
    server_url: str,
    algorithms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    server_id = await _ensure_server(db, server_url)
    synced: list[dict[str, Any]] = []

    seen: set[str] = set()
    for item in algorithms:
        algorithm_id = item.get("algorithm_id") or item.get("algorithmId") or item.get("model_id") or item.get("modelId") or item.get("id") or item.get("name")
        algorithm_name = item.get("algorithm_name") or item.get("algorithmName") or item.get("name") or item.get("algorithm_id") or algorithm_id
        if not algorithm_id or not algorithm_name:
            continue
        if str(algorithm_id) in seen:
            continue
        seen.add(str(algorithm_id))

        payload = {
            "serverId": server_id,
            "algorithmId": algorithm_id,
            "algorithmName": algorithm_name,
            "algorithmType": item.get("algorithm_type") or item.get("algorithmType") or item.get("type") or "icing",
            "version": item.get("version") or item.get("algorithm_version") or "v1.0",
            "description": item.get("description") or item.get("remark") or "Synced from algorithm-server",
            "runApi": item.get("run_api") or item.get("runApi") or "/api/tasks/run",
            "inputSchema": item.get("input_schema") or item.get("inputSchema") or "",
            "outputSchema": item.get("output_schema") or item.get("outputSchema") or "",
            "status": item.get("status") or "enabled",
            "preserveLocalStatus": True,
        }
        model = await create_model(db, payload)
        if model.get("status") != "deleted":
            synced.append(model)

    await _refresh_server_model_count(db, server_id)
    return synced


async def _refresh_server_model_count(db: AsyncSession, server_id: int | None) -> None:
    if server_id is None:
        return
    result = await db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM algorithm_model
            WHERE server_id = :server_id
              AND COALESCE(status, 'enabled') <> 'deleted'
        """),
        {"server_id": server_id},
    )
    count = int(result.fetchone()._mapping.get("cnt") or 0)
    await db.execute(text("""
        UPDATE algorithm_server
        SET model_count = :cnt, update_time = NOW()
        WHERE id = :server_id
    """), {"cnt": count, "server_id": server_id})
    await db.commit()
