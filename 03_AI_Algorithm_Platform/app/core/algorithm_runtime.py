from __future__ import annotations

import importlib.util
import mimetypes
import sys
from pathlib import Path
from typing import Any, Callable

from core.model_registry import get_model


def _load_entrypoint(package_path: Path, entrypoint: str, algorithm_id: str) -> Callable[[dict[str, Any]], Any]:
    module_ref, separator, function_name = entrypoint.partition(":")
    if not separator or not module_ref or not function_name:
        raise ValueError("算法入口格式必须为 runner.py:run")
    module_file = (package_path / module_ref).resolve()
    package_root = package_path.resolve()
    if package_root != module_file and package_root not in module_file.parents:
        raise ValueError("算法入口超出算法包目录")
    if not module_file.is_file():
        raise FileNotFoundError(f"算法入口文件不存在：{module_file}")

    module_name = f"uploaded_algorithm_{algorithm_id}_{module_file.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    if not spec or not spec.loader:
        raise ImportError(f"无法加载算法入口：{module_file}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(package_path))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(package_path))
        except ValueError:
            pass
    function = getattr(module, function_name, None)
    if not callable(function):
        raise AttributeError(f"算法入口函数不存在或不可调用：{entrypoint}")
    return function


def _normalize_file_result(result: Any, input_data: dict[str, Any]) -> Any:
    if isinstance(result, (str, Path)):
        result = {"output_file": str(result)}
    if not isinstance(result, dict) or not result.get("output_file"):
        return result

    output_file = Path(str(result.get("output_file"))).resolve()
    output_dir = Path(str(input_data.get("output_dir") or "")).resolve()
    if not output_file.is_file():
        raise FileNotFoundError(f"算法声明的结果文件不存在：{output_file}")
    if output_dir != output_file.parent and output_dir not in output_file.parents:
        raise ValueError("算法结果文件必须写入任务 output_dir")
    content_type = result.get("content_type") or mimetypes.guess_type(output_file.name)[0] or "application/octet-stream"
    return {
        **result,
        "result_type": "file",
        "output_file": str(output_file),
        "output_filename": result.get("output_filename") or output_file.name,
        "content_type": content_type,
    }


def run_registered_algorithm(algorithm_id: str, input_data: dict[str, Any]) -> Any:
    model = get_model(algorithm_id=algorithm_id) or get_model(model_id=algorithm_id)
    if not model or str(model.get("status") or "enabled") != "enabled":
        raise LookupError(f"未找到已启用算法：{algorithm_id}")
    package_path = Path(str(model.get("package_path") or ""))
    entrypoint = str(model.get("entrypoint") or "").strip()
    if not package_path.is_dir() or not entrypoint:
        raise LookupError(f"算法 {algorithm_id} 不是可执行算法包")
    function = _load_entrypoint(package_path, entrypoint, algorithm_id)
    return _normalize_file_result(function(input_data), input_data)
