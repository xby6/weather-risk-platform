from __future__ import annotations

import importlib
import json
import os
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
import yaml
from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.algorithm_runtime import run_registered_algorithm
from core.model_registry import delete_model as delete_registered_model
from core.model_registry import list_models as list_registered_models
from core.model_registry import register_model, save_uploaded_model
from core.task_store import TASK_STORE

standard_routes = APIRouter(prefix="/api", tags=["标准算法服务接口"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
ICING_FEATURE_ORDER = "temperature,humidity,wind_speed,wind_direction,precipitation,history_icing_thickness"
TASK_FILE_ROOT = PROJECT_ROOT / "task_files"


class TaskRunRequest(BaseModel):
    model_config = {"protected_namespaces": ()}

    task_id: str = Field(..., description="任务编号")
    algorithm_id: str = Field(..., description="算法编号或已上传模型编号")
    model_id: str | None = Field(default=None, description="可选：已上传模型编号")
    region: str | None = Field(default=None, description="预测区域")
    line_code: str | None = Field(default=None, description="线路编号")
    forecast_hours: int = Field(default=24, description="预测时长")
    features: list[dict[str, Any]] = Field(default_factory=list, description="气象特征")
    params: dict[str, Any] = Field(default_factory=dict, description="任务参数")


def _success(data: Any = None, msg: str = "操作成功") -> dict[str, Any]:
    return {
        "code": 200,
        "msg": msg,
        "success": True,
        "data": data,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _failure(msg: str, data: Any = None) -> dict[str, Any]:
    return {
        "code": 500,
        "msg": msg,
        "success": False,
        "data": data,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _load_config_algorithms() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        return config.get("algorithms", {}) or {}
    except Exception:
        return {}


def _builtin_algorithms() -> list[dict[str, Any]]:
    from algo.tabpfn_fault_cv import runtime_status
    from algo.tabpfn_fault_forecast import runtime_status as forecast_runtime_status

    tabpfn_runtime = runtime_status()
    tabpfn_forecast_runtime = forecast_runtime_status()
    return [
        {
            "algorithm_id": "tabpfn_fault_cv",
            "algorithm_name": "TabPFN故障杆塔交叉验证",
            "algorithm_type": "tabular_cv",
            "version": "v8.0.8",
            "description": "读取双行表头气象Excel，执行50次重复5折分层交叉验证，输出结果Excel。",
            "input_type": "xlsx",
            "input_schema": {
                "file": ".xlsx",
                "target_column": "是否为故障杆塔",
                "n_repeats": 50,
                "n_splits": 5,
            },
            "output_schema": {
                "type": "xlsx",
                "sheets": ["每折结果", "总体统计", "每个样本预测结果"],
            },
            "run_api": "/api/tasks/run-file",
            "can_run": bool(tabpfn_runtime.get("ready")),
            "runtime": tabpfn_runtime,
        },
        {
            "algorithm_id": "tabpfn_fault_forecast",
            "algorithm_name": "TabPFN杆塔故障概率预测",
            "algorithm_type": "tabular_forecast",
            "version": "v1.0.0",
            "description": "使用带故障标签的历史Excel训练TabPFN，对新的气象Excel输出未来杆塔故障概率、概率等级、评估表和图表。",
            "input_type": "xlsx_pair",
            "input_schema": {
                "training_file": ".xlsx，包含是否为故障杆塔标签",
                "prediction_file": ".xlsx，特征列与训练文件一致",
                "target_column": "是否为故障杆塔",
                "forecast_hours": "1-168",
            },
            "output_schema": {
                "type": "xlsx",
                "sheets": ["未来故障预测", "概率等级统计", "每折结果", "总体统计", "历史样本验证", "可视化图表"],
            },
            "run_api": "/api/tasks/run-file",
            "can_run": bool(tabpfn_forecast_runtime.get("ready")),
            "runtime": tabpfn_forecast_runtime,
        },
        {
            "algorithm_id": "icing_forecast",
            "algorithm_name": "输电线路覆冰厚度预测模型",
            "algorithm_type": "icing",
            "version": "v1.0",
            "description": "输入温度、湿度、风速、风向、降水、历史覆冰厚度，输出未来覆冰厚度、风险等级和 used_real_model。",
            "input_type": "json",
            "input_schema": {"features": ICING_FEATURE_ORDER.split(",")},
            "output_schema": {"future_icing_thickness": "float", "risk_level": "str", "used_real_model": "bool"},
            "run_api": "/api/tasks/run",
            "can_run": True,
        },
        {
            "algorithm_id": "wind_risk_forecast",
            "algorithm_name": "大风风险预测模型",
            "algorithm_type": "wind",
            "version": "v1.0",
            "description": "根据风速、风向和线路信息输出大风风险等级。",
            "input_type": "json",
            "run_api": "/api/tasks/run",
            "can_run": True,
        },
        {
            "algorithm_id": "comprehensive_risk",
            "algorithm_name": "综合电力气象风险评估模型",
            "algorithm_type": "composite",
            "version": "v1.0",
            "description": "综合覆冰、大风、降水等指标输出综合风险等级。",
            "input_type": "json",
            "run_api": "/api/tasks/run",
            "can_run": True,
        },
    ]


def _algorithm_list() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, info in _load_config_algorithms().items():
        rows.append({
            "algorithm_id": name,
            "algorithm_name": info.get("intro") or name,
            "algorithm_type": info.get("algorithm_type") or "legacy",
            "version": info.get("version") or "v1.0",
            "description": info.get("intro") or "原有算法服务算法",
            "input_type": "zip",
            "run_api": "/process",
            "can_run": True,
        })

    existing_ids = {item["algorithm_id"] for item in rows}
    for item in _builtin_algorithms():
        if item["algorithm_id"] not in existing_ids:
            rows.append(item)
            existing_ids.add(item["algorithm_id"])

    for model in list_registered_models(status="enabled"):
        algorithm_id = model.get("algorithm_id") or model.get("model_id")
        if not algorithm_id or algorithm_id in existing_ids:
            continue
        rows.append({
            "algorithm_id": algorithm_id,
            "model_id": model.get("model_id"),
            "algorithm_name": model.get("algorithm_name") or algorithm_id,
            "algorithm_type": model.get("algorithm_type") or "icing",
            "version": model.get("version") or "v1.0",
            "description": model.get("description") or "已上传到 algorithm-server 的真实模型",
            "input_type": model.get("input_type") or "json",
            "output_type": model.get("output_type") or "json",
            "run_api": model.get("run_api") or "/api/tasks/run",
            "entrypoint": model.get("entrypoint") or "",
            "can_run": True,
            "model_format": model.get("model_format"),
            "feature_order": model.get("feature_order"),
            "status": model.get("status") or "enabled",
        })
    return rows


def _resolve_algorithm_module(algorithm_id: str) -> str:
    try:
        from core.model_registry import get_model

        registered = get_model(algorithm_id=algorithm_id) or get_model(model_id=algorithm_id)
        if registered:
            if registered.get("entrypoint") and registered.get("package_path"):
                return "__registered_package__"
            algorithm_type = str(registered.get("algorithm_type") or "icing").strip().lower()
            if algorithm_type == "icing":
                return "icing_forecast"
            return "tabular_predict"
    except Exception:
        pass
    return algorithm_id


def _run_algorithm_task(task_id: str, algorithm_id: str, input_data: dict[str, Any]) -> None:
    try:
        TASK_STORE.update(task_id, status="running", progress=20, message="算法任务运行中")
        module_name = _resolve_algorithm_module(algorithm_id)
        if module_name == "__registered_package__":
            result = run_registered_algorithm(algorithm_id, input_data)
        else:
            module = importlib.import_module(f"algo.{module_name}")
            if hasattr(module, "run"):
                result = module.run(input_data)
            elif hasattr(module, "algorithm"):
                result = module.algorithm(input_data=input_data)
            else:
                raise RuntimeError(f"算法 {module_name} 缺少 run(input_data) 函数")
        TASK_STORE.update(task_id, status="success", progress=100, message="任务运行完成", result=result, error=None)
    except Exception as exc:
        TASK_STORE.update(
            task_id,
            status="failed",
            progress=100,
            message="任务运行失败",
            error=f"{exc}\n{traceback.format_exc()}",
        )


@standard_routes.get("/health", summary="算法服务器健康检查")
async def health() -> dict[str, Any]:
    from algo.tabpfn_fault_cv import runtime_status
    from algo.tabpfn_fault_forecast import runtime_status as forecast_runtime_status

    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory().percent
    return _success({
        "status": "online",
        "service": "algorithm-server",
        "version": "1.2.0-icing-runtime",
        "cpu_usage": cpu,
        "gpu_usage": 0,
        "memory_usage": memory,
        "pid": os.getpid(),
        "model_count": len(list_registered_models()),
        "capabilities": [
            "file_algorithm",
            "json_algorithm",
            "downloadable_result",
            "tabpfn_cross_validation",
            "tabpfn_fault_forecast",
            "icing_model_upload",
            "pkl_joblib",
            "torch_optional",
        ],
        "tabpfn": runtime_status(),
        "tabpfn_forecast": forecast_runtime_status(),
    })


@standard_routes.get("/algorithms", summary="获取算法列表")
async def algorithms() -> dict[str, Any]:
    return _success(_algorithm_list())


@standard_routes.get("/models", summary="获取已上传模型列表")
async def models() -> dict[str, Any]:
    return _success(list_registered_models())


@standard_routes.post("/models/register", summary="登记已存在模型文件")
async def register_model_api(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        model = register_model(payload)
        return _success(model, "模型已登记到 algorithm-server")
    except Exception as exc:
        return _failure(f"模型登记失败：{exc}")


@standard_routes.post("/models/upload", summary="上传模型文件到 algorithm-server 并登记")
async def upload_model_api(
    file: UploadFile = File(...),
    algorithmId: str = Form(...),
    algorithmName: str = Form(...),
    algorithmType: str = Form(default="icing"),
    version: str = Form(default="v1.0"),
    featureOrder: str = Form(default=ICING_FEATURE_ORDER),
    inputType: str = Form(default="json"),
    outputType: str = Form(default="json"),
    runApi: str = Form(default="/api/tasks/run"),
    entrypoint: str = Form(default=""),
    remark: str = Form(default=""),
) -> dict[str, Any]:
    try:
        content = await file.read()
        model = save_uploaded_model(
            file.filename or "model.bin",
            content,
            {
                "algorithmId": algorithmId,
                "algorithmName": algorithmName,
                "algorithmType": algorithmType or "icing",
                "version": version or "v1.0",
                "featureOrder": featureOrder,
                "inputType": inputType or "json",
                "outputType": outputType or "json",
                "runApi": runApi or "/api/tasks/run",
                "entrypoint": entrypoint or "",
                "remark": remark,
                "status": "enabled",
            },
        )
        return _success(model, "模型文件已上传到 algorithm-server，可用于真实任务执行")
    except Exception as exc:
        return _failure(f"模型上传失败：{exc}")


@standard_routes.delete("/models/{model_id}", summary="删除 algorithm-server 已上传模型")
async def delete_model_api(model_id: str) -> dict[str, Any]:
    ok = delete_registered_model(model_id)
    if ok:
        return _success({"model_id": model_id}, "模型已删除")
    return _failure("模型不存在", {"model_id": model_id})


@standard_routes.post("/tasks/run", summary="提交算法任务")
async def run_task(payload: TaskRunRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    input_data = payload.model_dump()
    if not input_data.get("model_id"):
        input_data["model_id"] = input_data.get("algorithm_id")
    TASK_STORE.create(payload.task_id, payload.algorithm_id, input_data)
    TASK_STORE.update(payload.task_id, status="running", progress=10, message="任务已提交到算法服务器")
    background_tasks.add_task(_run_algorithm_task, payload.task_id, payload.algorithm_id, input_data)
    return _success({
        "task_id": payload.task_id,
        "algorithm_id": payload.algorithm_id,
        "model_id": input_data.get("model_id"),
        "status": "running",
        "progress": 10,
        "message": "任务已提交",
    })


@standard_routes.post("/tasks/run-file", summary="提交原始文件算法任务")
async def run_file_task(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    trainingFile: UploadFile | None = File(default=None),
    taskId: str = Form(...),
    algorithmId: str = Form(...),
    modelId: str | None = Form(default=None),
    paramsJson: str = Form(default="{}"),
) -> dict[str, Any]:
    try:
        params = json.loads(paramsJson or "{}")
        if not isinstance(params, dict):
            raise ValueError("paramsJson must be a JSON object")
        safe_task_id = "".join(
            char if char.isalnum() or char in "-_" else "_" for char in taskId
        )
        safe_filename = Path(file.filename or "input.bin").name
        task_dir = TASK_FILE_ROOT / safe_task_id
        input_dir = task_dir / "input"
        output_dir = task_dir / "output"
        if task_dir.exists():
            shutil.rmtree(task_dir)
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        input_file = input_dir / safe_filename
        with input_file.open("wb") as target:
            shutil.copyfileobj(file.file, target)

        training_file: Path | None = None
        if trainingFile is not None:
            safe_training_name = Path(trainingFile.filename or "training.xlsx").name
            training_file = input_dir / f"training_{safe_training_name}"
            with training_file.open("wb") as target:
                shutil.copyfileobj(trainingFile.file, target)

        input_data = {
            "task_id": taskId,
            "algorithm_id": algorithmId,
            "model_id": modelId or algorithmId,
            "input_file": str(input_file),
            "output_dir": str(output_dir),
            "params": params,
        }
        if training_file is not None:
            input_data["training_file"] = str(training_file)
        TASK_STORE.create(taskId, algorithmId, input_data)
        TASK_STORE.update(taskId, status="running", progress=10, message="原始文件已接收，算法开始运行")
        background_tasks.add_task(_run_algorithm_task, taskId, algorithmId, input_data)
        return _success({
            "task_id": taskId,
            "algorithm_id": algorithmId,
            "status": "running",
            "progress": 10,
            "message": "原始文件已提交到算法服务",
        })
    except Exception as exc:
        return _failure(f"文件任务提交失败：{exc}")


@standard_routes.get("/tasks/status/{task_id}", summary="查询任务状态")
async def task_status(task_id: str) -> dict[str, Any]:
    record = TASK_STORE.get(task_id)
    if not record:
        return _failure("任务不存在", {"task_id": task_id, "status": "not_found"})
    return _success({
        "task_id": task_id,
        "algorithm_id": record.get("algorithm_id"),
        "status": record.get("status"),
        "progress": record.get("progress", 0),
        "message": record.get("message"),
        "error": record.get("error"),
    })


@standard_routes.get("/tasks/result/{task_id}", summary="获取任务结果")
async def task_result(task_id: str) -> dict[str, Any]:
    record = TASK_STORE.get(task_id)
    if not record:
        return _failure("任务不存在", {"task_id": task_id, "status": "not_found"})
    return _success({
        "task_id": task_id,
        "algorithm_id": record.get("algorithm_id"),
        "status": record.get("status"),
        "progress": record.get("progress", 0),
        "result": record.get("result"),
        "error": record.get("error"),
    })


@standard_routes.get("/tasks/result-file/{task_id}", summary="下载算法任务结果文件")
async def task_result_file(task_id: str):
    record = TASK_STORE.get(task_id)
    if not record or record.get("status") != "success":
        return _failure("任务尚未成功完成，暂无结果文件")
    result = record.get("result") or {}
    output_file = Path(str(result.get("output_file") or "")).resolve()
    task_root = (TASK_FILE_ROOT / "".join(
        char if char.isalnum() or char in "-_" else "_" for char in task_id
    )).resolve()
    if not output_file.is_file() or task_root not in output_file.parents:
        return _failure("任务结果文件不存在或路径无效")
    return FileResponse(
        output_file,
        media_type=result.get("content_type") or "application/octet-stream",
        filename=result.get("output_filename") or output_file.name,
    )


@standard_routes.get("/tasks", summary="获取算法服务器任务列表")
async def task_list() -> dict[str, Any]:
    return _success(TASK_STORE.list())
