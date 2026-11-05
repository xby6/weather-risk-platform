import json

from fastapi import APIRouter, UploadFile, File, Form, Response, Depends, Request
import asyncio
import os
import shutil
import tempfile
import logging
import traceback

from core.algorithm_executor import run_algorithm

# 创建路由实例
execution_routes = APIRouter()

@execution_routes.post("/process")
async def process_request(
    request: Request,
    file: UploadFile = File(...),
    task_id: str = Form(...),
    algo_name: str = Form(...),
    args_json: str = Form(...),
):
    # 获取请求状态中的进程管理器
    pm = request.app.state.pm
    # 解析 JSON 格式的参数
    args = json.loads(args_json)

    # 检查任务 ID 是否存在
    if not task_id:
        return Response(status_code=400, content="Missing task ID")

    # 创建临时目录用于存储任务相关文件
    temp_dir = tempfile.mkdtemp(prefix=f"task_{task_id}_")
    # 定义上传文件的存储路径
    zip_path = os.path.join(temp_dir, "uploaded.zip")

    try:
        # 将上传的文件写入临时路径
        with open(zip_path, "wb") as f:
            f.write(await file.read())

        # 创建新进程来运行算法
        p = pm.ctx.Process(
            target=run_algorithm,
            args=(task_id, temp_dir, args, pm.global_queue, algo_name)
        )
        p.start()

        # 创建一个异步 Future 对象用于等待任务结果
        future = asyncio.Future()
        # 加锁并将任务信息存入任务映射表
        async with pm.lock:
            pm.task_map[task_id] = (p, temp_dir, future)

        try:
            # 等待任务完成, 设置超时时间
            result = await asyncio.wait_for(future, timeout=10000000)
            logging.info(f"Task {task_id} completed successfully")
            return Response(content=result, media_type="application/zip")
        except asyncio.TimeoutError:
            # 任务超时, 终止进程
            p.terminate()
            return Response(status_code=504, content="Processing timeout")
        finally:
            # 清理临时目录
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        # 记录错误信息
        logging.error(f"Request failed: {traceback.format_exc()}")
        return Response(status_code=500, content=str(e))

@execution_routes.post("/stop")
async def stop(
    request: Request,
    task_id: str = Form(...),
):
    """终止运行中的任务"""
    # 获取请求状态中的进程管理器
    pm = request.app.state.pm
    # 加锁保证线程安全
    async with pm.lock:
        # 检查任务是否存在
        if task_id not in pm.task_map:
            return Response(status_code=404, content="Task not found")

        # 从任务映射表中取出任务信息
        p, temp_dir, future = pm.task_map.pop(task_id)

        try:
            # 如果进程仍在运行, 终止进程
            if p.is_alive():
                p.terminate()
                try:
                    # 等待进程结束, 最多等待 5 秒
                    p.join(timeout=5)
                except Exception:
                    # 若等待超时, 强制杀死进程
                    p.kill()

            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

            # 如果任务未完成, 设置异常标记任务被用户取消
            if not future.done():
                future.set_exception(asyncio.CancelledError("Task stopped by user"))

            return Response(status_code=200, content="Task stopped")
        except Exception as e:
            # 记录停止任务时的错误信息
            logging.error(f"Stop task failed: {traceback.format_exc()}")
            return Response(status_code=500, content=f"Stop failed: {str(e)}")
            
@execution_routes.get("/running-tasks")
async def get_running_tasks(request: Request):
    """获取正在运行的任务列表"""
    pm = request.app.state.pm
    async with pm.lock:
        # 遍历任务映射表, 检查进程是否还在运行
        running_tasks = []
        for task_id, (p, _, _) in pm.task_map.items():
            if p.is_alive():
                running_tasks.append(task_id)
        return {"running_tasks": running_tasks}

@execution_routes.get("/logs")
async def get_logs(request: Request):
    """获取任务执行日志"""
    try:
        # 假设日志文件路径在应用状态中存储
        log_file_path = 'app.log'
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8') as f:
                logs = f.read()
            return Response(content=logs, media_type="text/plain")
        else:
            return Response(status_code=404, content="Log file not found")
    except Exception as e:
        return Response(status_code=500, content=f"Failed to get logs: {str(e)}")
