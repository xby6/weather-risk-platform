import uvicorn  # py异步服务器，运行fastAPI之类的现代异步web框架，fastapi只是定义了接口规则，uvicorn让接口跑起来

from config.env import AppConfig
from server import create_app

if __name__ != '__main__':
    app = create_app()

if __name__ == '__main__':
    uvicorn.run(
        app='server:create_app',
        host=AppConfig.app_host,
        port=AppConfig.app_port,
        root_path=AppConfig.app_root_path,
        reload=AppConfig.app_reload,
        workers=AppConfig.app_workers,
        factory=True,
    )
