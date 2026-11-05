from __future__ import annotations

import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_seesion import DBSessionDependency
from module_admin.service.algorithm_client import AlgorithmClient, DEFAULT_ALGORITHM_SERVER_URL
from module_admin.service.algorithm_model_store import (
    create_model,
    delete_model,
    get_model_by_algorithm_id,
    list_models,
    sync_remote_algorithms,
    update_model_status,
    upload_model_file,
)
from module_admin.service.algorithm_result_preview import build_algorithm_result_preview
from module_admin.service.algorithm_server_store import (
    create_server,
    delete_server,
    get_server,
    list_servers,
    update_server_count,
    update_server_health,
)
from module_admin.service.algorithm_task_history import list_task_history
from module_admin.service.algorithm_task_store import claim_task_run, create_task, delete_task, get_task, list_tasks, update_task
from module_admin.service.weather_data_store import get_file as get_weather_file
from module_admin.service.weather_feature_parser import parse_weather_dataset
from utils.response_util import ResponseUtil

router = APIRouter(prefix="/algorithm", tags=["算法服务互连"])

ICING_FEATURE_ORDER = "temperature,humidity,wind_speed,wind_direction,precipitation,history_icing_thickness"
TASK_RESULT_DIR = Path("vf_admin/algorithm_results")
TABPFN_CV_ALGORITHM_ID = "tabpfn_fault_cv"
TABPFN_FORECAST_ALGORITHM_ID = "tabpfn_fault_forecast"


def _unwrap_algorithm_response(resp: Any) -> Any:
    if isinstance(resp, dict) and "data" in resp:
        return resp.get("data")
    return resp


def _safe_error_payload(exc: Exception) -> dict[str, Any]:
    return {
        "rows": [],
        "total": 0,
        "error": str(exc),
        "hint": "请确认已执行 sql/weather_power_business_tables.sql，并确认后端连接的是同一个 MySQL 库。",
    }


def _normalize_url(value: str | None) -> str:
    return str(value or "").strip().rstrip("/")


async def _resolve_server_url(db: AsyncSession, server_id: str | None, server_url: str | None) -> str:
    url = _normalize_url(server_url)
    if url:
        return url
    if server_id not in (None, ""):
        server = await get_server(db, server_id)
        if server and server.get("url"):
            return _normalize_url(server.get("url"))
    return DEFAULT_ALGORITHM_SERVER_URL


def _pick(params: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = params.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalized_icing_params(task: dict[str, Any]) -> dict[str, Any]:
    params = dict(task.get("params") or {})
    forecast_hours = int(task.get("forecastHours") or params.get("forecast_hours") or params.get("forecastHours") or 24)
    return {
        "temperature": _pick(params, "temperature"),
        "humidity": _pick(params, "humidity"),
        "wind_speed": _pick(params, "wind_speed", "windSpeed"),
        "wind_direction": _pick(params, "wind_direction", "windDirection"),
        "precipitation": _pick(params, "precipitation"),
        "history_icing_thickness": _pick(params, "history_icing_thickness", "historyIcingThickness", "icingThickness", "icing_thickness"),
        "forecast_hours": forecast_hours,
    }


def _build_features(params: dict[str, Any]) -> list[dict[str, Any]]:
    feature = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": params.get("temperature"),
        "humidity": params.get("humidity"),
        "wind_speed": params.get("wind_speed"),
        "wind_direction": params.get("wind_direction"),
        "precipitation": params.get("precipitation"),
        "history_icing_thickness": params.get("history_icing_thickness"),
        "icing_thickness": params.get("history_icing_thickness"),
    }
    if any(value not in (None, "") for key, value in feature.items() if key != "time"):
        return [feature]
    return []


def _is_file_algorithm(task: dict[str, Any], model: dict[str, Any] | None) -> bool:
    algorithm_id = str(task.get("algorithmId") or "").strip().lower()
    task_type = str(task.get("taskType") or "").strip().lower()
    algorithm_type = str((model or {}).get("algorithmType") or "").strip().lower()
    run_api = str((model or {}).get("runApi") or "").strip().lower()
    return (
        algorithm_id in {TABPFN_CV_ALGORITHM_ID, TABPFN_FORECAST_ALGORITHM_ID}
        or task_type in {"tabular_cv", "tabular_forecast", "file_algorithm"}
        or algorithm_type in {"tabular_cv", "tabular_forecast", "file_algorithm"}
        or run_api.endswith("/api/tasks/run-file")
    )


def _file_task_params(
    task: dict[str, Any],
    weather_file: dict[str, Any],
    training_file: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = dict(task.get("params") or {})
    algorithm_id = str(task.get("algorithmId") or "")
    if algorithm_id in {TABPFN_CV_ALGORITHM_ID, TABPFN_FORECAST_ALGORITHM_ID}:
        default_repeats = 50 if algorithm_id == TABPFN_CV_ALGORITHM_ID else 1
        params.update({
            "n_repeats": int(params.get("n_repeats") or params.get("nRepeats") or default_repeats),
            "n_splits": int(params.get("n_splits") or params.get("nSplits") or 5),
            "random_seed": int(params.get("random_seed") or params.get("randomSeed") or 42),
            "target_column": str(params.get("target_column") or params.get("targetColumn") or "是否为故障杆塔"),
        })
    if algorithm_id == TABPFN_FORECAST_ALGORITHM_ID:
        params.update({
            "forecast_hours": int(task.get("forecastHours") or params.get("forecast_hours") or 24),
            "fault_threshold": float(params.get("fault_threshold") or 0.5),
            "training_file_id": training_file.get("id") if training_file else params.get("training_file_id"),
            "training_file_name": (training_file.get("name") or training_file.get("originalName")) if training_file else params.get("training_file_name"),
        })
    return {
        **params,
        "source_file_id": weather_file.get("id"),
        "source_file_name": weather_file.get("name") or weather_file.get("originalName") or "",
    }


def _has_persisted_result(task: dict[str, Any]) -> bool:
    result = task.get("result")
    return result not in (None, {}, [])


def _result_filename(task_code: str, result: dict[str, Any]) -> str:
    raw_name = Path(str(result.get("output_filename") or result.get("output_file") or f"{task_code}_result.bin")).name
    safe_name = raw_name.replace("..", "_").replace("/", "_").replace("\\", "_")
    return safe_name or f"{task_code}_result.bin"


async def _cache_result_file(
    task: dict[str, Any],
    result: dict[str, Any],
    client: AlgorithmClient | None = None,
) -> str:
    if result.get("result_type") != "file":
        return task.get("resultPath") or ""

    current_path = Path(str(task.get("resultPath") or ""))
    if current_path.is_absolute() and current_path.is_file():
        return str(current_path.resolve())

    task_code = str(task.get("taskCode") or result.get("task_id") or "task")
    target_dir = TASK_RESULT_DIR / task_code
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _result_filename(task_code, result)

    source = Path(str(result.get("output_file") or ""))
    if source.is_absolute() and source.is_file():
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return str(target.resolve())

    if client is not None:
        content, _, _ = await client.task_result_file(task_code)
        target.write_bytes(content)
        return str(target.resolve())
    return task.get("resultPath") or ""


async def _persist_remote_result(
    db: AsyncSession,
    task: dict[str, Any],
    result_data: dict[str, Any],
    client: AlgorithmClient,
) -> dict[str, Any]:
    result = result_data.get("result")
    result_path = task.get("resultPath") or ""
    if isinstance(result, dict) and result.get("result_type") == "file":
        try:
            result_path = await _cache_result_file(task, result, client)
        except Exception:
            result_path = result_path or f"/algorithm/task/result-file/{task['taskCode']}"
    saved_task = await update_task(
        db,
        task["taskCode"],
        status=result_data.get("status", task.get("status")),
        progress=result_data.get("progress", task.get("progress", 0)),
        result=result,
        resultPath=result_path,
        error=result_data.get("error"),
        message="任务结果已写入数据库",
    ) or task
    # Report failures must not change a successfully persisted algorithm result.
    if saved_task.get("status") == "success":
        try:
            from module_admin.service.algorithm_report_store import enqueue_auto_report
            await enqueue_auto_report(db, saved_task)
        except Exception:
            await db.rollback()
            from utils.log_util import logger
            logger.warning('任务结果已保存，自动报告排队失败，后台将再次检查')
    return saved_task


async def _restore_persisted_result(db: AsyncSession, task: dict[str, Any]) -> dict[str, Any]:
    result = task.get("result")
    result_path = task.get("resultPath") or ""
    if isinstance(result, dict) and result.get("result_type") == "file":
        try:
            result_path = await _cache_result_file(task, result)
        except Exception:
            pass
    return await update_task(
        db,
        task["taskCode"],
        status="success",
        progress=100,
        resultPath=result_path,
        error=None,
        message="已从数据库读取历史任务结果",
    ) or task


async def _attach_result_preview(task: dict[str, Any]) -> dict[str, Any]:
    result = task.get("result")
    if (
        str(task.get("algorithmId") or "") != TABPFN_FORECAST_ALGORITHM_ID
        or not isinstance(result, dict)
        or result.get("result_type") != "file"
    ):
        return task
    try:
        result_path = await _cache_result_file(task, result)
        preview = await asyncio.to_thread(build_algorithm_result_preview, Path(result_path))
    except Exception as exc:
        preview = {"available": False, "message": f"结果预览生成失败：{exc}"}
    return {**task, "result": {**result, "preview": preview}}


@router.get("/server/list", summary="获取算力平台列表")
async def list_algorithm_servers(query_db: Annotated[AsyncSession, DBSessionDependency()]):
    try:
        rows = await list_servers(query_db)
        return ResponseUtil.success(data={"rows": rows, "total": len(rows)}, msg="算力平台列表获取成功")
    except Exception as exc:
        return ResponseUtil.success(data=_safe_error_payload(exc), msg=f"算力平台列表获取失败：{exc}")


@router.post("/server/create", summary="新增算力平台")
async def create_algorithm_server(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    payload: dict[str, Any] = Body(...),
):
    if not payload.get("url") and not payload.get("serverUrl"):
        return ResponseUtil.failure(msg="请填写算法服务地址")
    try:
        server = await create_server(query_db, payload)
        return ResponseUtil.success(data=server, msg="算力平台已保存")
    except Exception as exc:
        return ResponseUtil.failure(msg=f"算力平台保存失败：{exc}")


@router.delete("/server/{server_id}", summary="删除算力平台")
async def delete_algorithm_server(server_id: str, query_db: Annotated[AsyncSession, DBSessionDependency()]):
    try:
        ok = await delete_server(query_db, server_id)
        if ok:
            return ResponseUtil.success(msg="算力平台已删除")
        return ResponseUtil.failure(msg="算力平台不存在")
    except Exception as exc:
        return ResponseUtil.failure(msg=f"算力平台删除失败：{exc}")


@router.get("/server/health", summary="测试 algorithm-server 连接")
async def check_algorithm_server(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    serverUrl: str = Query(default=DEFAULT_ALGORITHM_SERVER_URL),
):
    server_url = _normalize_url(serverUrl) or DEFAULT_ALGORITHM_SERVER_URL
    try:
        data = await AlgorithmClient(server_url).health()
        health = _unwrap_algorithm_response(data)
        if isinstance(health, dict):
            try:
                await update_server_health(query_db, server_url, health)
            except Exception:
                pass
        return ResponseUtil.success(data=health, msg="algorithm-server 连接成功")
    except Exception as exc:
        return ResponseUtil.failure(
            data={"status": "offline", "serverUrl": server_url, "error": str(exc)},
            msg=f"algorithm-server 连接失败：{exc}",
        )


@router.get("/model/list", summary="获取已登记算法/模型列表")
async def list_algorithm_models(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    serverId: str | None = Query(default=None),
    serverUrl: str | None = Query(default=None),
):
    try:
        rows = await list_models(query_db, server_id=serverId, server_url=serverUrl)
        return ResponseUtil.success(data={"rows": rows, "total": len(rows)}, msg="算法模型列表获取成功")
    except Exception as exc:
        return ResponseUtil.success(data={"rows": [], "total": 0, "error": str(exc)}, msg=f"算法模型列表获取失败：{exc}")


@router.get("/model/db-list", summary="获取 MySQL 已登记算法/模型列表")
async def list_algorithm_models_from_db(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    serverId: str | None = Query(default=None),
    serverUrl: str | None = Query(default=None),
):
    rows = await list_models(query_db, server_id=serverId, server_url=serverUrl)
    return ResponseUtil.success(data={"rows": rows, "total": len(rows)}, msg="算法模型列表获取成功")


@router.post("/model/create", summary="登记算法/模型")
async def create_algorithm_model(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    payload: dict[str, Any] = Body(...),
):
    try:
        model = await create_model(query_db, payload)
        return ResponseUtil.success(data=model, msg="算法/模型已登记")
    except Exception as exc:
        return ResponseUtil.failure(msg=f"算法/模型登记失败：{exc}")


@router.post("/model/upload", summary="上传模型文件并登记算法/模型")
async def upload_algorithm_model(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    file: UploadFile = File(...),
    serverId: str | None = Form(default=None),
    serverUrl: str | None = Form(default=None),
    algorithmId: str = Form(...),
    algorithmName: str = Form(...),
    algorithmType: str | None = Form(default="icing"),
    version: str | None = Form(default="v1.0"),
    runApi: str | None = Form(default="/api/tasks/run"),
    featureOrder: str | None = Form(default=ICING_FEATURE_ORDER),
    inputType: str | None = Form(default="json"),
    outputType: str | None = Form(default="json"),
    entrypoint: str | None = Form(default=""),
    remark: str | None = Form(default=""),
):
    server_url = await _resolve_server_url(query_db, serverId, serverUrl)
    payload = {
        "serverId": serverId,
        "serverUrl": server_url,
        "algorithmId": algorithmId,
        "algorithmName": algorithmName,
        "algorithmType": algorithmType or "icing",
        "version": version or "v1.0",
        "runApi": runApi or "/api/tasks/run",
        "inputSchema": {
            "input_type": inputType or "json",
            "features": [item.strip() for item in str(featureOrder or "").split(",") if item.strip()],
            "entrypoint": entrypoint or "",
        },
        "outputSchema": {"output_type": outputType or "json"},
        "remark": remark or "",
        "status": "enabled",
    }

    try:
        content = await file.read()
        await file.seek(0)
        remote_result = None
        remote_error = None
        try:
            remote_resp = await AlgorithmClient(server_url).upload_model(
                file.filename or "model.bin",
                content,
                {
                    "algorithmId": algorithmId,
                    "algorithmName": algorithmName,
                    "algorithmType": algorithmType or "icing",
                    "version": version or "v1.0",
                    "featureOrder": featureOrder or ICING_FEATURE_ORDER,
                    "inputType": inputType or "json",
                    "outputType": outputType or "json",
                    "runApi": runApi or "/api/tasks/run",
                    "entrypoint": entrypoint or "",
                    "remark": remark or "",
                },
            )
            remote_result = _unwrap_algorithm_response(remote_resp)
            if isinstance(remote_result, dict):
                payload["remoteModelId"] = remote_result.get("model_id") or remote_result.get("algorithm_id")
        except Exception as remote_exc:
            remote_error = str(remote_exc)

        await file.seek(0)
        model = await upload_model_file(query_db, file, payload)
        model["remoteModel"] = remote_result
        model["remoteError"] = remote_error
        if remote_error:
            return ResponseUtil.success(
                data=model,
                msg=f"模型已保存到 RuoYi，但同步 algorithm-server 失败：{remote_error}",
            )
        return ResponseUtil.success(data=model, msg="模型文件已保存、登记并同步到 algorithm-server")
    except Exception as exc:
        return ResponseUtil.failure(msg=f"模型上传失败：{exc}")


@router.post("/model/sync", summary="从 algorithm-server 同步算法/模型到 MySQL")
async def sync_algorithm_models(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    serverUrl: str = Query(default=DEFAULT_ALGORITHM_SERVER_URL),
):
    server_url = _normalize_url(serverUrl) or DEFAULT_ALGORITHM_SERVER_URL
    try:
        client = AlgorithmClient(server_url)
        combined: list[dict[str, Any]] = []

        try:
            algorithms = _unwrap_algorithm_response(await client.algorithms())
            if isinstance(algorithms, list):
                combined.extend(algorithms)
        except Exception:
            pass

        try:
            models = _unwrap_algorithm_response(await client.models())
            if isinstance(models, list):
                combined.extend(models)
        except Exception:
            pass

        rows = await sync_remote_algorithms(query_db, server_url, combined)
        try:
            await update_server_count(query_db, server_url, model_count=len(rows))
        except Exception:
            pass
        return ResponseUtil.success(data={"rows": rows, "total": len(rows)}, msg="算法/模型同步成功")
    except Exception as exc:
        return ResponseUtil.failure(data={"rows": [], "total": 0, "error": str(exc)}, msg=f"算法/模型同步失败：{exc}")


@router.put("/model/{model_id}/status", summary="启用/停用算法模型")
async def change_algorithm_model_status(
    model_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    payload: dict[str, Any] = Body(...),
):
    model = await update_model_status(query_db, model_id, payload.get("status") or "enabled")
    if not model:
        return ResponseUtil.failure(msg="算法/模型不存在")
    return ResponseUtil.success(data=model, msg="状态已更新")


@router.delete("/model/{model_id}", summary="删除已登记算法/模型")
async def delete_algorithm_model(model_id: str, query_db: Annotated[AsyncSession, DBSessionDependency()]):
    ok = await delete_model(query_db, model_id)
    if ok:
        return ResponseUtil.success(msg="算法/模型已逻辑删除")
    return ResponseUtil.failure(msg="算法/模型不存在")


@router.get("/task/list", summary="获取算法任务列表")
async def get_algorithm_task_list(query_db: Annotated[AsyncSession, DBSessionDependency()]):
    try:
        rows = await list_tasks(query_db)
        return ResponseUtil.success(data={"rows": rows, "total": len(rows)}, msg="任务列表获取成功")
    except Exception as exc:
        return ResponseUtil.success(data=_safe_error_payload(exc), msg=f"任务列表获取失败：{exc}")


@router.get("/task/history/{task_code}", summary="分页查询任务运行记录")
async def get_algorithm_task_history(
    task_code: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    page_num: int = Query(1, alias="pageNum", ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
):
    if not await get_task(query_db, task_code):
        return ResponseUtil.failure(msg="任务不存在")
    data = await list_task_history(query_db, task_code, page_num, page_size)
    return ResponseUtil.success(data=data, msg="任务运行记录获取成功")


@router.post("/task/create", summary="创建算法任务")
async def create_algorithm_task(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    payload: dict[str, Any] = Body(...),
):
    if not payload.get("algorithmId") and not payload.get("algorithm"):
        return ResponseUtil.failure(msg="请选择真实算法模型")
    if not payload.get("serverUrl"):
        return ResponseUtil.failure(msg="请选择算力平台或填写 algorithm-server 地址")
    if payload.get("fileId") not in (None, ""):
        weather_file = await get_weather_file(query_db, payload.get("fileId"))
        if not weather_file:
            return ResponseUtil.failure(msg="所选气象数据文件不存在，请刷新文件列表后重试")
        if weather_file.get("itemType") == "folder" or weather_file.get("isFolder"):
            return ResponseUtil.failure(msg="不能选择文件夹作为任务输入文件")
    if str(payload.get("algorithmId") or "") == TABPFN_FORECAST_ALGORITHM_ID:
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        training_file_id = params.get("training_file_id") or params.get("trainingFileId")
        if payload.get("fileId") in (None, ""):
            return ResponseUtil.failure(msg="TabPFN 杆塔故障预测必须选择待预测数据文件")
        if training_file_id in (None, ""):
            return ResponseUtil.failure(msg="TabPFN 杆塔故障预测必须选择历史训练文件")
        if str(training_file_id) == str(payload.get("fileId")):
            return ResponseUtil.failure(msg="历史训练文件和待预测文件不能是同一个文件")
        training_file = await get_weather_file(query_db, training_file_id)
        if not training_file:
            return ResponseUtil.failure(msg="所选历史训练文件不存在，请刷新文件列表后重试")
        if training_file.get("itemType") == "folder" or training_file.get("isFolder"):
            return ResponseUtil.failure(msg="不能选择文件夹作为历史训练文件")
    try:
        task = await create_task(query_db, payload)
        return ResponseUtil.success(data=task, msg="任务创建成功")
    except Exception as exc:
        return ResponseUtil.failure(msg=f"任务创建失败：{exc}")


@router.post("/task/run/{task_code}", summary="提交任务到 algorithm-server 运行")
async def run_algorithm_task(task_code: str, query_db: Annotated[AsyncSession, DBSessionDependency()]):
    task = await get_task(query_db, task_code)
    if not task:
        return ResponseUtil.failure(msg="任务不存在")
    if task.get("status") in {"running", "queued", "submitted"}:
        return ResponseUtil.failure(msg="任务正在执行，请等待完成后再运行")
    if not task.get("algorithmId"):
        return ResponseUtil.failure(msg="任务缺少算法模型，无法运行")
    if not task.get("serverUrl"):
        return ResponseUtil.failure(msg="任务缺少 algorithm-server 地址，无法运行")

    model = await get_model_by_algorithm_id(
        query_db,
        task.get("algorithmId"),
        server_id=task.get("serverId"),
        server_url=task.get("serverUrl"),
    )
    if model and model.get("status") != "enabled":
        return ResponseUtil.failure(msg="当前算法模型已停用，不能运行任务")

    if _is_file_algorithm(task, model):
        try:
            if task.get("fileId") in (None, ""):
                raise ValueError("文件型算法必须选择气象 Excel 文件")
            weather_file = await get_weather_file(query_db, task.get("fileId"))
            if not weather_file:
                raise ValueError("所选气象数据文件不存在")
            if weather_file.get("itemType") == "folder" or weather_file.get("isFolder"):
                raise ValueError("不能选择文件夹作为任务输入文件")
            file_path = Path(str(weather_file.get("filePath") or "")).resolve()
            if not file_path.is_file():
                raise FileNotFoundError(f"气象数据文件不存在：{file_path}")
            algorithm_id = str(task.get("algorithmId") or "")
            if algorithm_id in {TABPFN_CV_ALGORITHM_ID, TABPFN_FORECAST_ALGORITHM_ID} and file_path.suffix.lower() not in {".xlsx", ".xls"}:
                raise ValueError("TabPFN 算法仅支持 Excel .xlsx/.xls 文件")

            training_file = None
            training_filename = None
            training_content = None
            if algorithm_id == TABPFN_FORECAST_ALGORITHM_ID:
                training_file_id = (task.get("params") or {}).get("training_file_id")
                if training_file_id in (None, ""):
                    raise ValueError("TabPFN 杆塔故障预测缺少历史训练文件")
                training_file = await get_weather_file(query_db, training_file_id)
                if not training_file:
                    raise ValueError("所选历史训练文件不存在")
                if training_file.get("itemType") == "folder" or training_file.get("isFolder"):
                    raise ValueError("不能选择文件夹作为历史训练文件")
                training_path = Path(str(training_file.get("filePath") or "")).resolve()
                if not training_path.is_file():
                    raise FileNotFoundError(f"历史训练文件不存在：{training_path}")
                if training_path.suffix.lower() not in {".xlsx", ".xls"}:
                    raise ValueError("历史训练文件必须是 Excel .xlsx/.xls 文件")
                training_filename = training_file.get("originalName") or training_file.get("name") or training_path.name
                training_content = training_path.read_bytes()

            params = _file_task_params(task, weather_file, training_file)
            if not await claim_task_run(query_db, task_code):
                return ResponseUtil.failure(msg="任务已在执行或不存在，请刷新任务列表")
            result = _unwrap_algorithm_response(
                await AlgorithmClient(task.get("serverUrl")).run_file_task(
                    weather_file.get("originalName") or weather_file.get("name") or file_path.name,
                    file_path.read_bytes(),
                    task_id=task["taskCode"],
                    algorithm_id=task.get("algorithmId"),
                    model_id=task.get("algorithmId"),
                    params=params,
                    training_filename=training_filename,
                    training_content=training_content,
                )
            )
            updated = await update_task(
                query_db,
                task_code,
                status=result.get("status", "running") if isinstance(result, dict) else "running",
                progress=result.get("progress", 10) if isinstance(result, dict) else 10,
                message=result.get("message", "原始文件已提交到 algorithm-server") if isinstance(result, dict) else "原始文件已提交到 algorithm-server",
                params=params,
                result=None,
                resultPath="",
                error=None,
            )
            return ResponseUtil.success(data=updated, msg="文件任务已提交到 algorithm-server")
        except Exception as exc:
            updated = await update_task(
                query_db,
                task_code,
                status="failed",
                progress=100,
                message="文件任务提交失败",
                error=str(exc),
            )
            return ResponseUtil.failure(msg=f"文件任务提交失败：{exc}", data=updated)

    params = _normalized_icing_params(task)

    features = _build_features(params)
    if task.get("fileId") not in (None, ""):
        try:
            weather_file = await get_weather_file(query_db, task.get("fileId"))
            if not weather_file:
                raise ValueError("所选气象数据文件不存在")
            if weather_file.get("itemType") == "folder" or weather_file.get("isFolder"):
                raise ValueError("不能选择文件夹作为任务输入文件")
            parsed = parse_weather_dataset(weather_file.get("filePath") or "")
            features = parsed.get("samples") or []
            if not features:
                raise ValueError("气象数据文件没有可执行样本")
            params = {
                **params,
                "batch_mode": True,
                "source_type": "weather_file",
                "source_file_id": weather_file.get("id"),
                "source_file_name": weather_file.get("name") or parsed.get("file_name"),
                "source_record_count": parsed.get("record_count"),
                "source_feature_count": parsed.get("feature_count"),
                "source_header_row": parsed.get("header_row"),
                "feature_names": parsed.get("feature_names") or [],
                "target_column": parsed.get("target_column"),
                "target_distribution": parsed.get("target_distribution") or {},
            }
        except Exception as exc:
            updated = await update_task(
                query_db,
                task_code,
                status="failed",
                progress=100,
                message="气象数据文件解析失败",
                error=str(exc),
            )
            return ResponseUtil.failure(msg=f"气象数据文件解析失败：{exc}", data=updated)

    payload = {
        "task_id": task["taskCode"],
        "algorithm_id": task.get("algorithmId"),
        "model_id": task.get("algorithmId"),
        "region": task.get("region") or None,
        "line_code": task.get("lineCode") or None,
        "forecast_hours": params["forecast_hours"],
        "features": features,
        "params": params,
    }

    try:
        if not await claim_task_run(query_db, task_code):
            return ResponseUtil.failure(msg="任务已在执行或不存在，请刷新任务列表")
        result = _unwrap_algorithm_response(await AlgorithmClient(task.get("serverUrl")).run_task(payload))
        updated = await update_task(
            query_db,
            task_code,
            status=result.get("status", "running") if isinstance(result, dict) else "running",
            progress=result.get("progress", 10) if isinstance(result, dict) else 10,
            message=result.get("message", "任务已提交到 algorithm-server") if isinstance(result, dict) else "任务已提交到 algorithm-server",
            params=params,
        )
        return ResponseUtil.success(data=updated, msg="任务已提交到 algorithm-server")
    except Exception as exc:
        updated = await update_task(query_db, task_code, status="failed", progress=100, message="提交失败", error=str(exc))
        return ResponseUtil.failure(msg=f"任务提交失败：{exc}", data=updated)


@router.get("/task/status/{task_code}", summary="查询 algorithm-server 任务状态")
async def get_algorithm_task_status(task_code: str, query_db: Annotated[AsyncSession, DBSessionDependency()]):
    task = await get_task(query_db, task_code)
    if not task:
        return ResponseUtil.failure(msg="任务不存在")
    try:
        client = AlgorithmClient(task.get("serverUrl"))
        status_data = _unwrap_algorithm_response(await client.task_status(task_code))
        if isinstance(status_data, dict):
            if status_data.get("status") == "success":
                result_data = _unwrap_algorithm_response(await client.task_result(task_code))
                updated = await _persist_remote_result(query_db, task, result_data, client)
            else:
                updated = await update_task(
                    query_db,
                    task_code,
                    status=status_data.get("status", task.get("status")),
                    progress=status_data.get("progress", task.get("progress", 0)),
                    message=status_data.get("message", task.get("message")),
                    error=status_data.get("error"),
                )
        else:
            updated = task
        return ResponseUtil.success(data=updated, msg="任务状态获取成功")
    except Exception as exc:
        if _has_persisted_result(task):
            updated = await _restore_persisted_result(query_db, task)
            return ResponseUtil.success(data=updated, msg="algorithm-server 无运行记录，已使用数据库历史结果")
        return ResponseUtil.failure(msg=f"任务状态查询失败：{exc}", data=task)


@router.get("/task/result/{task_code}", summary="获取 algorithm-server 任务结果")
async def get_algorithm_task_result(task_code: str, query_db: Annotated[AsyncSession, DBSessionDependency()]):
    task = await get_task(query_db, task_code)
    if not task:
        return ResponseUtil.failure(msg="任务不存在")
    if _has_persisted_result(task):
        updated = await _restore_persisted_result(query_db, task)
        return ResponseUtil.success(data=await _attach_result_preview(updated), msg="历史任务结果已从数据库读取")
    try:
        client = AlgorithmClient(task.get("serverUrl"))
        result_data = _unwrap_algorithm_response(await client.task_result(task_code))
        if isinstance(result_data, dict):
            updated = await _persist_remote_result(query_db, task, result_data, client)
        else:
            updated = await update_task(query_db, task_code, result=result_data, message="任务结果获取成功")
        return ResponseUtil.success(data=await _attach_result_preview(updated), msg="任务结果获取成功")
    except Exception as exc:
        return ResponseUtil.failure(msg=f"任务结果获取失败，数据库中也没有可用结果：{exc}", data=task)


@router.get("/task/result-file/{task_code}", summary="下载算法任务结果文件")
async def download_algorithm_task_result(task_code: str, query_db: Annotated[AsyncSession, DBSessionDependency()]):
    task = await get_task(query_db, task_code)
    if not task:
        return ResponseUtil.failure(msg="任务不存在")
    if task.get("status") != "success" and not _has_persisted_result(task):
        return ResponseUtil.failure(msg="任务尚未成功完成，暂无结果文件")
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    try:
        local_path = await _cache_result_file(task, result)
        local_file = Path(str(local_path or ""))
        if local_file.is_absolute() and local_file.is_file():
            if local_path != task.get("resultPath"):
                await update_task(query_db, task_code, resultPath=str(local_file.resolve()))
            return FileResponse(
                local_file,
                media_type=result.get("content_type") or "application/octet-stream",
                filename=result.get("output_filename") or local_file.name,
            )
    except Exception:
        pass
    try:
        content, content_type, disposition = await AlgorithmClient(task.get("serverUrl")).task_result_file(task_code)
        headers = {"Content-Disposition": disposition} if disposition else {}
        return Response(content=content, media_type=content_type, headers=headers)
    except Exception as exc:
        return ResponseUtil.failure(msg=f"结果文件下载失败：{exc}")


@router.delete("/task/{task_code}", summary="删除本地任务记录")
async def delete_algorithm_task(task_code: str, query_db: Annotated[AsyncSession, DBSessionDependency()]):
    ok = await delete_task(query_db, task_code)
    if ok:
        return ResponseUtil.success(msg="任务删除成功")
    return ResponseUtil.failure(msg="任务不存在")
