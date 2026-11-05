import asyncio
import importlib
import logging
import os
import shutil
import traceback
from multiprocessing import Queue
import queue

async def result_listener(pm):
    """安全增强型结果监听循环"""
    while getattr(pm, "running", True):
        try:
            item = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: pm.global_queue.get(block=True, timeout=0.5)
                ),
                timeout=1.5
            )
            async with pm.lock:
                task_id, result = item
                logging.info(f"Received result for task {task_id}")

                if task_id in pm.task_map:
                    p, temp_dir, future = pm.task_map.pop(task_id)
                    if not future.done():
                        if isinstance(result, tuple) and len(result) >= 2 and result[0] == "ERROR":
                            future.set_exception(Exception(result[1]))
                        else:
                            future.set_result(result)
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
        except (asyncio.TimeoutError, queue.Empty):
            continue
        except Exception as e:
            if pm.running:
                logging.error(f"监听错误: {str(e)}")
            else:
                break

def run_algorithm(task_id: str, temp_dir: str, args: dict, queue: Queue, algo_name: str):
    """安全封装的算法执行函数"""
    try:
        zip_path = os.path.join(temp_dir, "uploaded.zip")
        module = importlib.import_module(f"algo.{algo_name}")
        algorithm = getattr(module, "algorithm")
        result = algorithm(zip_path=zip_path, **args)
        queue.put((task_id, result))
    except Exception as e:
        queue.put((task_id, ("ERROR", str(e))))
        logging.error(f"Algorithm failed: {traceback.format_exc()}")