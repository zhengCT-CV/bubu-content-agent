"""Windows 本地开发使用的 FastAPI 启动入口。

Uvicorn 新版本在 Windows 上会主动创建 ProactorEventLoop，但 psycopg 的异步
连接只支持 SelectorEventLoop。这里显式提供兼容的 loop factory，避免服务在
初始化 PostgreSQL/LangGraph checkpoint 时失败。
"""

from __future__ import annotations

import asyncio
import sys

import uvicorn

from app.config import get_settings


def local_loop_factory() -> asyncio.AbstractEventLoop:
    """为 Windows 返回 psycopg 兼容循环，其他系统使用 Python 默认循环。"""

    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def main() -> None:
    """读取统一配置并启动本地 API；不启用 reload，便于可靠管理进程树。"""

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        loop="app.serve_api:local_loop_factory",
    )


if __name__ == "__main__":
    main()
