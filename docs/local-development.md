# 开发与验证

[项目首页](../README.md) · [系统架构](architecture.md)

这里保留维护者需要的服务和验证入口。项目业务介绍与运行画面见[业务图集](business-workflow.md)，无需启动服务即可浏览。

## 本地服务依赖

Python 3.11、Node.js、pnpm、Docker Desktop。真实服务模式还需要 DeepSeek / DashScope 密钥，以及由使用者维护的运营资料目录。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
pnpm --dir frontend install
Copy-Item .env.example .env
```

仅首次创建配置时复制示例文件，已有 `.env` 不要覆盖。编辑配置：

- `APP_MODE=local`
- `DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`：使用自己的密钥。
- `WRITEBACK_APPROVAL_SECRET`：只保存在服务端的随机长字符串。
- `WECHAT_WORKSPACE_PATH`：指向自己的运营资料目录；示例中的路径不能直接视为可用数据。

私有运营数据与真实密钥不包含在公开仓库中。不要提交 `.env`、数据库、日志或未经检查的业务导出。

## 服务管理

```powershell
.\scripts\start-local.ps1 -OpenBrowser
.\scripts\status-local.ps1
.\scripts\stop-local.ps1
```

启动脚本管理 PostgreSQL/pgvector、Redis、MCP、FastAPI、ARQ Worker 和 React。日志位于忽略提交的 `.runtime/logs/`。Docker Compose 只承载数据库与 Redis，其余进程在主机运行。

停止时默认保留基础设施；需要停止数据库和 Redis 可使用 `stop-local.ps1 -StopInfrastructure`，卷数据保留。

这些是本地开发脚本，不是公网部署方案。当前缺少登录和公网权限控制，不应直接将 API、MCP 或数据库端口开放到互联网。

## 测试与构建

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check backend mcp_server tests
pnpm --dir frontend build
```

自动化测试覆盖确定性逻辑、接口与工作流契约。真实模型输出质量、预测准确性和业务收益需要另外设计评测，不从测试通过或运行截图推导。
