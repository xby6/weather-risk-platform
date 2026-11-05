from __future__ import annotations

import json
import mimetypes
import os
from typing import Any

import httpx


DEFAULT_ALGORITHM_SERVER_URL = os.getenv("ALGORITHM_SERVER_URL", "http://127.0.0.1:8000")


class AlgorithmClient:
    """Small async client for the standalone algorithm-server."""

    def __init__(self, server_url: str | None = None, token: str | None = None) -> None:
        self.server_url = (server_url or DEFAULT_ALGORITHM_SERVER_URL).rstrip("/")
        self.token = token or os.getenv("ALGORITHM_SERVER_TOKEN", "")

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _response_json(response: httpx.Response) -> dict[str, Any]:
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and (payload.get("success") is False or payload.get("code") not in (None, 200)):
            raise RuntimeError(str(payload.get("msg") or payload.get("message") or "algorithm-server 调用失败"))
        return payload

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.server_url}/api/health", headers=self._headers())
            return self._response_json(response)

    async def algorithms(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{self.server_url}/api/algorithms", headers=self._headers())
            return self._response_json(response)

    async def models(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{self.server_url}/api/models", headers=self._headers())
            return self._response_json(response)

    async def register_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.server_url}/api/models/register", json=payload, headers=self._headers())
            return self._response_json(response)

    async def upload_model(self, filename: str, content: bytes, fields: dict[str, Any]) -> dict[str, Any]:
        data = {key: str(value) for key, value in fields.items() if value is not None}
        files = {"file": (filename or "model.bin", content, "application/octet-stream")}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.server_url}/api/models/upload",
                data=data,
                files=files,
                headers=self._headers(),
            )
            return self._response_json(response)

    async def delete_model(self, model_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(f"{self.server_url}/api/models/{model_id}", headers=self._headers())
            return self._response_json(response)

    async def run_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.server_url}/api/tasks/run", json=payload, headers=self._headers())
            return self._response_json(response)

    async def run_file_task(
        self,
        filename: str,
        content: bytes,
        *,
        task_id: str,
        algorithm_id: str,
        model_id: str | None = None,
        params: dict[str, Any] | None = None,
        training_filename: str | None = None,
        training_content: bytes | None = None,
    ) -> dict[str, Any]:
        data = {
            "taskId": task_id,
            "algorithmId": algorithm_id,
            "modelId": model_id or algorithm_id,
            "paramsJson": json.dumps(params or {}, ensure_ascii=False),
        }
        files = {
            "file": (
                filename or "input.bin",
                content,
                mimetypes.guess_type(filename or "")[0] or "application/octet-stream",
            )
        }
        if training_filename and training_content is not None:
            files["trainingFile"] = (
                training_filename,
                training_content,
                mimetypes.guess_type(training_filename)[0] or "application/octet-stream",
            )
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.server_url}/api/tasks/run-file",
                data=data,
                files=files,
                headers=self._headers(),
            )
            return self._response_json(response)

    async def task_status(self, task_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.server_url}/api/tasks/status/{task_id}", headers=self._headers())
            return self._response_json(response)

    async def task_result(self, task_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.server_url}/api/tasks/result/{task_id}", headers=self._headers())
            return self._response_json(response)

    async def task_result_file(self, task_id: str) -> tuple[bytes, str, str]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(
                f"{self.server_url}/api/tasks/result-file/{task_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "application/octet-stream")
            if "application/json" in content_type:
                payload = response.json()
                if isinstance(payload, dict) and (payload.get("success") is False or payload.get("code") not in (None, 200)):
                    raise RuntimeError(str(payload.get("msg") or "结果文件下载失败"))
            disposition = response.headers.get("content-disposition", "")
            return response.content, content_type, disposition
