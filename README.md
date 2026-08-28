# Bubu ContentOps Agent

一个面向微信公众号条漫创作的全栈 Agent 项目：从运营证据出发生成三个选题，经过人工选择、分镜编辑、逐格视觉 Prompt 审批、发布登记，再用 24h/48h 真实指标复盘并受控写回知识库。

它适合作为 Agent 开发实习项目展示，因为不是“套一层聊天 UI”：LangGraph 状态机、多 Agent 隔离、版本化 Skills、分层 RAG、独立 MCP、异步 API/Worker、checkpoint 时间回溯和人机协作都能在演示中看到。

## 关键边界

- 生成分镜与绘图 Prompt，不生成图片。
- 不自动发布公众号。
- Excel/CSV 始终只读。
- 未经人工批准，不写回 Markdown。
- 首版单用户本地运行，不含登录、多租户和公网部署。

## 目录

```text
backend/app/       FastAPI、LangGraph、Agents、Skills、RAG、仓储、Worker
frontend/src/      React 工作台、审批卡、证据侧栏、时间线
mcp_server/app/    微信运营 Resources、Tools 与文件适配器
infra/             PostgreSQL/pgvector、Redis 初始化
tests/             单元、API、Graph、MCP 安全与 Agent eval
docs/              架构、学习说明、演示脚本
```

## 先跑无密钥 Demo

要求：Python 3.11、Node.js、pnpm。以下命令在项目根目录 PowerShell 执行。

```powershell
D:\anaconda3\envs\agent\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
pnpm --dir frontend install
Copy-Item .env.example .env
```

确认 `.env` 中 `APP_MODE=demo`。分别打开两个终端：

```powershell
# 终端 1：API（从项目根目录启动，root 与 backend 都在导入路径中）
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload

# 终端 2：前端
pnpm --dir frontend dev
```

访问 `http://localhost:5173`。Demo 使用确定性 Agent、内存仓储与内存 checkpoint，不需要 Docker、Redis、DeepSeek 或 DashScope；它仍会只读访问 `.env` 配置的运营项目来演示证据检索。

## 切换完整 Local 模式

1. 安装并启动 Docker Desktop。
2. 填写 `.env`：

```dotenv
APP_MODE=local
DEEPSEEK_API_KEY=...
DASHSCOPE_API_KEY=...
WRITEBACK_APPROVAL_SECRET=一个只保存在本机的随机长字符串
WECHAT_WORKSPACE_PATH=C:\Users\10534\Documents\New project 2
```

3. 一键启动完整 Local 模式：

```powershell
.\scripts\start-local.ps1 -OpenBrowser
```

脚本会依次检查配置，启动 PostgreSQL/pgvector、Redis、MCP、FastAPI、ARQ Worker 与 React，并把后台日志写入 `.runtime/logs/`。

日常查看状态和停止：

```powershell
# 查看 Docker、主机进程和 HTTP 健康状态
.\scripts\status-local.ps1

# 只停止 API、MCP、Worker 和前端；数据库继续运行
.\scripts\stop-local.ps1

# 同时暂停 PostgreSQL 与 Redis，Volume 中的数据仍保留
.\scripts\stop-local.ps1 -StopInfrastructure
```

需要逐个观察进程输出、排查问题时，也可以手动启动四个主机进程：

```powershell
# API
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload

# 独立 MCP
.\.venv\Scripts\python.exe -m mcp_server.app.server

# ARQ Worker（PowerShell 当前会话加入 backend）
$env:PYTHONPATH="$PWD\backend;$PWD"
.\.venv\Scripts\arq.exe app.workers.settings.WorkerSettings

# React
pnpm --dir frontend dev
```

`docker compose` 只承载 PostgreSQL/pgvector 和 Redis，避免 Windows 中文路径挂载；API、MCP、Worker、React 都在主机运行。
根目录的 `sitecustomize.py` 会在 Windows 上自动为这些 Python 进程启用 psycopg 所需的 Selector 事件循环；无需手动设置。

## 测试与构建

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check backend mcp_server tests
pnpm --dir frontend build
```

## API

- `POST /api/projects`：创建作品。
- `POST /api/projects/{id}/runs`：启动 Graph。
- `GET /api/runs/{thread_id}/events`：SSE。
- `POST /api/runs/{thread_id}/resume`：审批、编辑或重生成。
- `GET /api/runs/{thread_id}/state`：当前状态。
- `GET /api/runs/{thread_id}/history`：checkpoint 历史。
- `POST /api/runs/{thread_id}/fork`：从旧 checkpoint 创建新 thread。
- `POST /api/projects/{id}/publish`：登记发布。
- `POST /api/projects/{id}/sync-metrics`：立即同步。
- `GET /api/projects/{id}/metrics`：指标快照。

更多说明见 [架构文档](docs/architecture.md)、[学习指南](docs/learning-guide.md)、[Visual Prompt v1.1 说明](docs/visual-prompt-v1.1.md) 和 [项目演示脚本](docs/demo-script.md)。
