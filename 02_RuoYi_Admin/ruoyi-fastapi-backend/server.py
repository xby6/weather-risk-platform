import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from common.constant import LockConstant
from common.router import auto_register_routers
from config.env import AppConfig
from config.get_db import close_async_engine, init_create_table
from config.get_redis import RedisUtil
from config.get_scheduler import SchedulerUtil
from exceptions.handle import handle_exception
from middlewares.handle import handle_middleware
from module_admin.service.log_service import LogAggregatorService
from sub_applications.handle import handle_sub_applications
from utils.common_util import worship
from utils.log_util import logger
from utils.server_util import APIDocsUtil, IPUtil, StartupUtil
from utils.transport_crypto_util import TransportKeyProvider


async def _start_background_tasks(app: FastAPI) -> None:
    """
    启动应用后台任务。

    当前项目保留真实 Redis 连接，但不启动日志聚合消费任务，
    避免低版本 Redis 不支持 XAUTOCLAIM 导致后端持续报错。
    """
    await SchedulerUtil.init_system_scheduler(app.state.redis)

    # 低版本 Redis 不支持 XAUTOCLAIM；先关闭日志聚合后台任务。
    # 不影响登录、菜单、气象数据、任务管理、算力平台和大屏接口。
    app.state.log_aggregator_task = None
    from module_admin.service.algorithm_report_service import report_queue_loop, report_source_loop
    app.state.report_queue_task = asyncio.create_task(report_queue_loop())
    app.state.report_source_task = asyncio.create_task(report_source_loop())


async def _stop_background_tasks(app: FastAPI) -> None:
    """
    停止应用后台任务并释放资源

    :param app: FastAPI对象
    :return: None
    """
    report_tasks = [getattr(app.state, name, None) for name in ('report_queue_task', 'report_source_task')]
    for task in report_tasks:
        if task:
            task.cancel()
    await asyncio.gather(*(task for task in report_tasks if task), return_exceptions=True)
    log_task = getattr(app.state, 'log_aggregator_task', None)
    if log_task:
        log_task.cancel()
        try:
            await log_task
        except asyncio.CancelledError:
            pass
    lock_task = getattr(app.state, 'lock_renewal_task', None)
    if lock_task:
        lock_task.cancel()
        try:
            await lock_task
        except asyncio.CancelledError:
            pass
    await RedisUtil.close_redis_pool(app)
    await SchedulerUtil.close_system_scheduler()
    await close_async_engine()


# 生命周期事件：启动时连接真实 Redis，关闭时释放 Redis / 数据库 / 定时任务
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f'{AppConfig.app_name}开始启动')

    # 初始化数据库连接；不会替代你手动导入业务 SQL，只负责确认连接和自动建 ORM 表
    await init_create_table()

    # 连接真实 Redis。配置来自 .env.dev / .env.prod 中的 REDIS_HOST、REDIS_PORT、REDIS_PASSWORD、REDIS_DATABASE
    app.state.redis = await RedisUtil.create_redis_pool()

    # 初始化系统字典、系统参数缓存
    await RedisUtil.init_sys_dict(app.state.redis)
    await RedisUtil.init_sys_config(app.state.redis)

    # 启动定时任务、登录日志聚合等后台任务；这些依赖真实 Redis Stream
    await _start_background_tasks(app)

    logger.info(f'{AppConfig.app_name}启动成功')

    try:
        yield
    finally:
        await _stop_background_tasks(app)
        logger.info(f'{AppConfig.app_name}停止运行')


def create_app() -> FastAPI:
    """
    创建FastAPI应用

    :return: FastAPI对象
    """
    # 配置API文档静态资源
    APIDocsUtil.setup_docs_static_resources()
    # 初始化FastAPI对象
    app = FastAPI(
        title=AppConfig.app_name,
        description=f'{AppConfig.app_name}接口文档',
        version=AppConfig.app_version,
        lifespan=lifespan,
        openapi_url=APIDocsUtil.proxy_openapi_url(),
        docs_url=APIDocsUtil.proxy_docs_url(),
        redoc_url=APIDocsUtil.proxy_redoc_url(),
        swagger_ui_oauth2_redirect_url=APIDocsUtil.proxy_oauth2_redirect_url(),
    )

    # 自定义API文档路由，修复无法直接通过后端地址访问文档的问题
    APIDocsUtil.custom_api_docs_router(app)

    # 挂载子应用
    handle_sub_applications(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:6688", "http://127.0.0.1:6688"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 加载中间件处理方法
    handle_middleware(app)
    # 加载全局异常处理方法
    handle_exception(app)
    # 自动注册路由
    auto_register_routers(app)

    # 业务互联路由兜底注册：避免自动扫描漏掉普通 APIRouter 时前端页面 404/空白。
    # 如果自动扫描已经注册过，按 marker 跳过，避免重复注册同一路径。
    def include_router_once(router_obj, marker_path: str):
        existing_paths = {getattr(route, 'path', '') for route in app.routes}
        if marker_path not in existing_paths:
            app.include_router(router_obj)

    from module_admin.controller.algorithm_link_controller import router as algorithm_link_router
    from module_admin.controller.screen_controller import router as screen_monitor_router
    from module_admin.controller.weather_data_controller import router as weather_data_router
    from module_admin.controller.algorithm_report_controller import router as algorithm_report_router

    include_router_once(algorithm_link_router, '/algorithm/server/list')
    include_router_once(screen_monitor_router, '/monitor/screen-all-data')
    include_router_once(weather_data_router, '/weather-file/list')
    include_router_once(algorithm_report_router, '/algorithm/report/config')
    return app
