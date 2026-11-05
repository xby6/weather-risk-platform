"""
轻量任务状态存储。
用于 algorithm-server 的标准 JSON 任务接口：
/api/tasks/run、/api/tasks/status/{task_id}、/api/tasks/result/{task_id}

说明：
- 当前使用进程内存储，重启服务后任务记录会清空；
- 后续正式部署时可以替换为 Redis / MySQL；
- 不影响原有 /process ZIP 图像算法接口。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TASK_STORE_PATH = PROJECT_ROOT / "task_store.json"


class TaskStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._tasks: dict[str, dict[str, Any]] = self._load()

    @staticmethod
    def _load() -> dict[str, dict[str, Any]]:
        if not TASK_STORE_PATH.is_file():
            return {}
        try:
            data = json.loads(TASK_STORE_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self) -> None:
        temporary = TASK_STORE_PATH.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._tasks, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        temporary.replace(TASK_STORE_PATH)

    def create(self, task_id: str, algorithm_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "task_id": task_id,
            "algorithm_id": algorithm_id,
            "status": "queued",
            "progress": 0,
            "message": "任务已创建，等待运行",
            "input_data": input_data,
            "result": None,
            "error": None,
            "create_time": now,
            "update_time": now,
        }
        with self._lock:
            self._tasks[task_id] = record
            self._save()
        return record

    def update(self, task_id: str, **kwargs: Any) -> dict[str, Any] | None:
        with self._lock:
            record = self._tasks.get(task_id)
            if not record:
                return None
            record.update(kwargs)
            record["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save()
            return dict(record)

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._tasks.get(task_id)
            return dict(record) if record else None

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._tasks.values()]


TASK_STORE = TaskStore()
