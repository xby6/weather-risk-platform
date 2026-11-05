from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log")],
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
for path in (APP_DIR, PROJECT_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BaseModel.model_config["protected_namespaces"] = ()

from api.algorithm_routes import algorithm_routes
from api.execution_routes import execution_routes
from api.model_routes import model_routes
from api.standard_routes import standard_routes
from core.algorithm_executor import result_listener
from core.process_manager import ProcessManager


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pm = ProcessManager()
        app.state.pm = pm
        try:
            pm.initialize()
            app.state.result_listener_task = asyncio.create_task(result_listener(pm))
        except Exception as exc:
            logging.warning("ProcessManager 初始化失败，旧 /process ZIP 接口可能不可用：%s", exc)
        try:
            yield
        finally:
            try:
                async with pm.lock:
                    for process, temp_dir, _ in pm.task_map.values():
                        if process.is_alive():
                            process.terminate()
                        shutil.rmtree(temp_dir, ignore_errors=True)
                pm.shutdown()
            except Exception as exc:
                logging.warning("ProcessManager 关闭异常：%s", exc)

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(standard_routes)
    app.include_router(algorithm_routes)
    app.include_router(model_routes)
    app.include_router(execution_routes)
    return app


if __name__ == "__main__":
    from multiprocessing import freeze_support

    import uvicorn

    freeze_support()
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
