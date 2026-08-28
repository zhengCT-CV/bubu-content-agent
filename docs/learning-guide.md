# 学习指南：按组件理解这个项目

## 1. 先把它看成四个进程

1. React：展示状态，收集人工决定。
2. FastAPI：提供 REST/SSE，把请求交给工作流。
3. MCP：把旧运营项目变成有边界的数据服务。
4. Worker：即使没有打开页面，也会定时检查 24h/48h 数据。

PostgreSQL、Redis、DeepSeek 和 DashScope 是依赖服务，不是第五个 Agent。

## 2. FastAPI 里面是什么

`app/main.py` 只负责应用生命周期、CORS、路由和错误处理。`container.py` 在启动时根据 `APP_MODE` 组装依赖：demo 使用内存仓储和确定性模型，local 使用 PostgreSQL、DeepSeek、DashScope 与 HTTP MCP。

路由不写业务逻辑。例如 `/resume` 只校验 `ResumeRequest` 并调用 `WorkflowService.resume()`。这样 Graph 测试无需启动 HTTP。

## 3. LangGraph 为什么是核心

普通“调用 LLM 一次”的代码无法自然表示：等用户选题、进程重启、24 小时以后继续、从旧版本分叉。Graph 把每一步表示为节点，把去哪里表示为边，把全部业务上下文放进 `AgentState`。

`interrupt()` 会保存 checkpoint 并暂停。用户点击批准后，FastAPI 发送 `Command(resume=...)`，同一个节点从 interrupt 返回处继续。不要把批准结果放在全局变量里，否则重启会丢。

## 4. Agent、Skill 和节点不是一回事

- Agent：调用模型并输出 Pydantic Schema，例如 `StoryboardAgent`。
- Skill：某项业务能力的版本化说明、Prompt、规则、示例和 eval。
- Node：工作流的一步，可以是 Agent 节点，也可以是纯代码节点。

`ReviewerAgent` 与创作 Agent 使用不同 Skill 和独立模型调用。Reviewer 不直接改稿，只返回阻断问题与返工指令。Graph 控制最多两轮自动返工，避免无限循环。

## 5. 版本化 Skill 怎么工作

每个 Skill 的 `manifest.yaml` 指向 `versions/1.0.0`。`SkillRegistry` 合并 `SKILL.md + prompt.md + rules.yaml` 计算 SHA-256。checkpoint 保存名称、版本和 hash。

以后修改提示词时应创建 `versions/1.1.0`，再把 `current_version` 改为 `1.1.0`。不要覆盖 `1.0.0`，否则旧 checkpoint 无法准确重放。

## 6. RAG 的三层

- 长期：`content_playbook.md`，权威但对近期变化不敏感。
- 近期：周复盘，权重最高，反映最近趋势。
- 案例：单篇记录，适合查相似题材、标题和失败原因。

`KnowledgeSource` 通过 MCP Resource 获取正文，`chunk_markdown()` 按标题切块，`PostgresHybridIndex` 保存向量。`HybridRagService` 再把语义、全文、来源权重和时间权重重排成 `EvidenceCitation`。

## 7. MCP 在这里解决什么

MCP 不是为了“看起来高级”。它隔离新 Agent 和旧数据仓库：新后端不需要了解工作簿每个 sheet，也不能随手改文件。以后数据源换成数据库，只需要改 MCP Adapter。

Resource 用于读可引用的上下文，Tool 用于带参数的精确查询或受控动作。所有 `openpyxl` 阻塞读取都用 `asyncio.to_thread()`，避免卡住 FastAPI 事件循环。

## 8. 异步与 SSE

启动 Graph 的接口返回 `202`，真正运行在后台任务里。节点先把事件写入仓储，再广播到 `EventBroker`。SSE 断线重连时先回放历史事件，再接收实时事件。

结构化模型输出目前按“产物级”流式展示；如果以后需要真实 token 流，可在 ModelGateway 增加 callback，把增量统一转成 `token.delta`，而不修改前端协议。

## 9. Worker 与里程碑

ARQ cron 每小时检查 `waiting_metrics` 项目。标题先标准化，再按发布时间窗口匹配。零匹配继续等；多匹配返回人工选择；唯一匹配才读取曲线。

只有最新采样达到 24h 或 48h，Worker 才恢复 Graph。任务、同步和写回都有幂等保护，所以重试不会重复落数据。

## 10. 推荐学习顺序

1. 跑 demo，看四次人工暂停。
2. 读 `domain/models.py` 和 `domain/state.py`，理解数据结构。
3. 读 `graphs/main_graph.py`，画出节点和边。
4. 读一个 Agent 和一个 Skill，对比“模型代码”和“业务说明”。
5. 读 MCP Adapter 的路径白名单。
6. 最后再看 PostgreSQL、pgvector、ARQ 与 provider 接口。

这样能先掌握 Agent 的骨架，再学习基础设施，不会一开始被组件数量淹没。

