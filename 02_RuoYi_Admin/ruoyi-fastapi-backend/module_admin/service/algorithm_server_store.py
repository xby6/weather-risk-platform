from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _row_to_vo(row: Any) -> dict[str, Any]:
    m = row._mapping if hasattr(row, "_mapping") else row
    return {
        "id": str(m.get("id")),
        "serverId": str(m.get("id")),
        "name": m.get("server_name") or "",
        "serverName": m.get("server_name") or "",
        "url": m.get("server_url") or "",
        "serverUrl": m.get("server_url") or "",
        "token": m.get("access_token") or "",
        "status": m.get("status") or "unknown",
        "cpuUsage": m.get("cpu_usage"),
        "gpuUsage": m.get("gpu_usage"),
        "memoryUsage": m.get("memory_usage"),
        "modelCount": m.get("model_count") or 0,
        "taskCount": m.get("task_count") or 0,
        "lastHeartbeat": str(m.get("last_heartbeat") or ""),
        "remark": m.get("remark") or "",
        "createBy": m.get("create_by") or "",
        "createTime": str(m.get("create_time") or ""),
        "updateTime": str(m.get("update_time") or ""),
    }


async def list_servers(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(text("""
        SELECT id, server_name, server_url, access_token, status, cpu_usage, gpu_usage, memory_usage,
               model_count, task_count, last_heartbeat, remark, create_by, create_time, update_time
        FROM algorithm_server
        ORDER BY update_time DESC, id DESC
    """))
    return [_row_to_vo(row) for row in result.fetchall()]


async def get_server(db: AsyncSession, server_id: str | int) -> dict[str, Any] | None:
    result = await db.execute(text("""
        SELECT id, server_name, server_url, access_token, status, cpu_usage, gpu_usage, memory_usage,
               model_count, task_count, last_heartbeat, remark, create_by, create_time, update_time
        FROM algorithm_server
        WHERE id = :id
        LIMIT 1
    """), {"id": int(server_id)})
    row = result.fetchone()
    return _row_to_vo(row) if row else None


async def get_server_by_url(db: AsyncSession, server_url: str) -> dict[str, Any] | None:
    result = await db.execute(text("""
        SELECT id, server_name, server_url, access_token, status, cpu_usage, gpu_usage, memory_usage,
               model_count, task_count, last_heartbeat, remark, create_by, create_time, update_time
        FROM algorithm_server
        WHERE server_url = :server_url
        LIMIT 1
    """), {"server_url": str(server_url or "").rstrip("/")})
    row = result.fetchone()
    return _row_to_vo(row) if row else None


async def create_server(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    server_url = str(payload.get("url") or payload.get("serverUrl") or payload.get("server_url") or "").rstrip("/")
    if not server_url:
        raise ValueError("算法服务地址不能为空")

    server_name = str(payload.get("name") or payload.get("serverName") or payload.get("server_name") or server_url).strip()
    token = payload.get("token") or payload.get("accessToken") or payload.get("access_token") or ""
    remark = payload.get("remark") or ""
    create_by = payload.get("createBy") or payload.get("create_by") or ""

    existing = await get_server_by_url(db, server_url)
    if existing:
        await db.execute(text("""
            UPDATE algorithm_server
            SET server_name = :server_name,
                access_token = :access_token,
                remark = :remark,
                create_by = :create_by,
                update_time = NOW()
            WHERE id = :id
        """), {
            "id": int(existing["id"]),
            "server_name": server_name,
            "access_token": token,
            "remark": remark,
            "create_by": create_by,
        })
        await db.commit()
        return await get_server(db, existing["id"]) or existing

    result = await db.execute(text("""
        INSERT INTO algorithm_server
        (server_name, server_url, access_token, status, remark, create_by, create_time, update_time)
        VALUES
        (:server_name, :server_url, :access_token, 'unknown', :remark, :create_by, NOW(), NOW())
    """), {
        "server_name": server_name,
        "server_url": server_url,
        "access_token": token,
        "remark": remark,
        "create_by": create_by,
    })
    await db.commit()
    return await get_server(db, result.lastrowid) or {"id": str(result.lastrowid), "name": server_name, "url": server_url}


async def update_server_health(db: AsyncSession, server_url: str, health: dict[str, Any]) -> None:
    await db.execute(text("""
        UPDATE algorithm_server
        SET status = :status,
            cpu_usage = :cpu_usage,
            gpu_usage = :gpu_usage,
            memory_usage = :memory_usage,
            last_heartbeat = NOW(),
            update_time = NOW()
        WHERE server_url = :server_url
    """), {
        "server_url": str(server_url or "").rstrip("/"),
        "status": health.get("status") or "online",
        "cpu_usage": health.get("cpu_usage") if health.get("cpu_usage") is not None else health.get("cpuUsage"),
        "gpu_usage": health.get("gpu_usage") if health.get("gpu_usage") is not None else health.get("gpuUsage"),
        "memory_usage": health.get("memory_usage") if health.get("memory_usage") is not None else health.get("memoryUsage"),
    })
    await db.commit()


async def update_server_count(
    db: AsyncSession,
    server_url: str,
    model_count: int | None = None,
    task_count: int | None = None,
) -> None:
    sets = ["update_time = NOW()"]
    params: dict[str, Any] = {"server_url": str(server_url or "").rstrip("/")}
    if model_count is not None:
        sets.append("model_count = :model_count")
        params["model_count"] = int(model_count)
    if task_count is not None:
        sets.append("task_count = :task_count")
        params["task_count"] = int(task_count)
    await db.execute(text(f"UPDATE algorithm_server SET {', '.join(sets)} WHERE server_url = :server_url"), params)
    await db.commit()


async def delete_server(db: AsyncSession, server_id: str | int) -> bool:
    result = await db.execute(text("DELETE FROM algorithm_server WHERE id = :id"), {"id": int(server_id)})
    await db.commit()
    return bool(result.rowcount)
