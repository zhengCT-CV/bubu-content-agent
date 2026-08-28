"""项目内 Python 进程的启动兼容设置。

Python 会在解释器启动阶段自动导入可见的 ``sitecustomize``。Windows 默认的
ProactorEventLoop 不受 psycopg 异步连接支持，因此 API、ARQ Worker 和测试统一
切换为 Selector 策略。Linux/macOS 不受影响。
"""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
