from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "uploaded_models"
ALGORITHM_PACKAGE_DIR = PROJECT_ROOT / "uploaded_algorithms"
REGISTRY_PATH = PROJECT_ROOT / "model_registry.json"
DEFAULT_FEATURE_ORDER = [
    "temperature",
    "humidity",
    "wind_speed",
    "wind_direction",
    "precipitation",
    "history_icing_thickness",
]

_LOCK = Lock()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_filename(name: str) -> str:
    return (name or "model.bin").replace("..", "_").replace("/", "_").replace("\\", "_")


def _load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"models": []}
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"models": []}
        models = data.get("models")
        if not isinstance(models, list):
            data["models"] = []
        return data
    except Exception:
        return {"models": []}


def _save_registry(data: dict[str, Any]) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_feature_order(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        order = [str(item).strip() for item in value if str(item).strip()]
        return order or DEFAULT_FEATURE_ORDER
    return DEFAULT_FEATURE_ORDER


def list_models(algorithm_type: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    with _LOCK:
        rows = list(_load_registry().get("models", []))
    if algorithm_type:
        rows = [row for row in rows if str(row.get("algorithm_type") or "") == str(algorithm_type)]
    if status:
        rows = [row for row in rows if str(row.get("status") or "") == str(status)]
    return rows


def get_model(model_id: str | None = None, algorithm_id: str | None = None) -> dict[str, Any] | None:
    for row in list_models():
        if model_id and str(row.get("model_id")) == str(model_id):
            return row
        if algorithm_id and str(row.get("algorithm_id")) == str(algorithm_id):
            return row
    return None


def get_active_model_for_algorithm(
    algorithm_id: str | None = None,
    algorithm_type: str | None = None,
) -> dict[str, Any] | None:
    rows = list_models(status="enabled")
    if algorithm_id:
        for row in rows:
            if str(row.get("algorithm_id")) == str(algorithm_id) or str(row.get("model_id")) == str(algorithm_id):
                return row
    if algorithm_type:
        typed = [row for row in rows if str(row.get("algorithm_type") or "") == str(algorithm_type)]
        if typed:
            return sorted(typed, key=lambda row: str(row.get("update_time") or row.get("create_time") or ""), reverse=True)[0]
    return None


def register_model(payload: dict[str, Any]) -> dict[str, Any]:
    algorithm_id = str(
        payload.get("algorithm_id")
        or payload.get("algorithmId")
        or payload.get("model_id")
        or payload.get("modelId")
        or f"model_{uuid4().hex[:8]}"
    ).strip()
    model_id = str(payload.get("model_id") or payload.get("modelId") or algorithm_id).strip()
    algorithm_name = str(payload.get("algorithm_name") or payload.get("algorithmName") or algorithm_id).strip()
    algorithm_type = str(payload.get("algorithm_type") or payload.get("algorithmType") or "icing").strip() or "icing"
    model_path = str(payload.get("model_path") or payload.get("modelPath") or payload.get("file_path") or payload.get("filePath") or "")
    model_format = str(
        payload.get("model_format")
        or payload.get("modelFormat")
        or (Path(model_path).suffix.lower().lstrip(".") if model_path else "")
    )
    feature_order = _normalize_feature_order(payload.get("feature_order") or payload.get("featureOrder"))
    input_type = str(payload.get("input_type") or payload.get("inputType") or "json")
    output_type = str(payload.get("output_type") or payload.get("outputType") or "json")
    default_output_schema = (
        {"result_type": "file", "output_type": output_type}
        if input_type == "file" or output_type != "json"
        else
        {
            "prediction": "number|string",
            "predicted_fault": "bool|null",
            "fault_probability": "float|null",
            "used_real_model": "bool",
        }
        if algorithm_type != "icing"
        else {
            "future_icing_thickness": "float",
            "risk_level": "str",
            "used_real_model": "bool",
        }
    )

    row = {
        "model_id": model_id,
        "algorithm_id": algorithm_id,
        "algorithm_name": algorithm_name,
        "algorithm_type": algorithm_type,
        "version": payload.get("version") or payload.get("algorithm_version") or "v1.0",
        "status": payload.get("status") or "enabled",
        "model_path": model_path,
        "model_file": Path(model_path).name if model_path else "",
        "model_format": model_format,
        "package_path": str(payload.get("package_path") or payload.get("packagePath") or ""),
        "entrypoint": str(payload.get("entrypoint") or ""),
        "input_type": input_type,
        "output_type": output_type,
        "run_api": str(payload.get("run_api") or payload.get("runApi") or "/api/tasks/run"),
        "feature_order": feature_order,
        "input_schema": payload.get("input_schema") or payload.get("inputSchema") or ({"type": "file"} if input_type == "file" else {"features": feature_order}),
        "output_schema": payload.get("output_schema") or payload.get("outputSchema") or default_output_schema,
        "description": payload.get("description") or payload.get("remark") or "",
        "create_time": payload.get("create_time") or _now(),
        "update_time": _now(),
    }

    with _LOCK:
        data = _load_registry()
        rows = data.setdefault("models", [])
        replaced = False
        for idx, old in enumerate(rows):
            if str(old.get("model_id")) == model_id or str(old.get("algorithm_id")) == algorithm_id:
                row["create_time"] = old.get("create_time") or row["create_time"]
                rows[idx] = {**old, **row}
                replaced = True
                break
        if not replaced:
            rows.append(row)
        _save_registry(data)
    return row


def save_uploaded_model(filename: str, content: bytes, payload: dict[str, Any]) -> dict[str, Any]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_filename(filename)
    algorithm_id = str(payload.get("algorithm_id") or payload.get("algorithmId") or Path(safe).stem or "icing_model").strip()
    suffix = Path(safe).suffix.lower()
    manifest: dict[str, Any] = {}
    package_path = ""
    entrypoint = str(payload.get("entrypoint") or "").strip()

    if suffix == ".zip" or (suffix == ".py" and entrypoint):
        package_dir = ALGORITHM_PACKAGE_DIR / algorithm_id
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True, exist_ok=True)
        if suffix == ".zip":
            archive_path = package_dir / safe
            archive_path.write_bytes(content)
            with zipfile.ZipFile(archive_path) as archive:
                root = package_dir.resolve()
                for member in archive.infolist():
                    destination = (package_dir / member.filename).resolve()
                    if root != destination and root not in destination.parents:
                        raise ValueError(f"算法包包含非法路径：{member.filename}")
                archive.extractall(package_dir)
            manifest_path = package_dir / "algorithm_manifest.json"
            if manifest_path.is_file():
                loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    manifest = loaded
            target = archive_path
        else:
            target = package_dir / safe
            target.write_bytes(content)
        package_path = str(package_dir)
    else:
        target = MODEL_DIR / f"{algorithm_id}_{safe}"
        target.write_bytes(content)

    merged = {**manifest, **payload}
    return register_model({
        **merged,
        "model_id": merged.get("model_id") or merged.get("modelId") or algorithm_id,
        "algorithm_id": algorithm_id,
        "model_path": str(target),
        "model_format": target.suffix.lower().lstrip("."),
        "package_path": package_path,
        "entrypoint": entrypoint or str(manifest.get("entrypoint") or ""),
    })


def delete_model(model_id: str) -> bool:
    removed = False
    with _LOCK:
        data = _load_registry()
        rows = data.setdefault("models", [])
        kept = []
        for row in rows:
            if str(row.get("model_id")) == str(model_id) or str(row.get("algorithm_id")) == str(model_id):
                removed = True
                try:
                    path = Path(str(row.get("model_path") or ""))
                    if path.exists() and path.is_file():
                        path.unlink()
                    package_path = Path(str(row.get("package_path") or ""))
                    if package_path.exists() and package_path.is_dir() and ALGORITHM_PACKAGE_DIR.resolve() in package_path.resolve().parents:
                        shutil.rmtree(package_path)
                except Exception:
                    pass
            else:
                kept.append(row)
        data["models"] = kept
        _save_registry(data)
    return removed
