# 代码导览

[项目首页](../README.md) · [业务图集](business-workflow.md) · [架构说明](architecture.md)

可以从界面能力直接定位实现，不必先运行服务。

## 从页面找到业务链路

| 想了解什么 | 前端入口 | 后端入口 |
| --- | --- | --- |
| 作品创建与当前状态 | [ProjectsPage](../frontend/src/pages/ProjectsPage.tsx) | [projects.py](../backend/app/api/projects.py) |
| 选题、分镜与 Prompt 人工审批 | [features/](../frontend/src/features/) | [main_graph.py](../backend/app/graphs/main_graph.py) |
| 证据来源与检索降级 | [EvidenceSidebar](../frontend/src/features/evidence/EvidenceSidebar.tsx) | [hybrid.py](../backend/app/rag/hybrid.py) |
| 节点进度与事件时间线 | [use-run-events](../frontend/src/api/use-run-events.ts) | [events.py](../backend/app/graphs/events.py) |
| 模型输入输出与错误定位 | [LlmTracesPage](../frontend/src/pages/LlmTracesPage.tsx) | [llm.py](../backend/app/integrations/llm.py) |
| 历史 checkpoint 与 Fork | [HistoryPage](../frontend/src/pages/HistoryPage.tsx) | [service.py](../backend/app/graphs/service.py) |
| 作品数据与采集状态 | [DataCenterPage](../frontend/src/pages/DataCenterPage.tsx) | [content_data.py](../backend/app/domain/content_data.py) |
| 发布后复盘与知识更新 | [KnowledgeGate](../frontend/src/features/approval/KnowledgeGate.tsx) | [tasks.py](../backend/app/workers/tasks.py)、[writeback.py](../backend/app/domain/writeback.py) |

## 推荐阅读顺序

1. **模型与状态**：[domain/models.py](../backend/app/domain/models.py)、[domain/state.py](../backend/app/domain/state.py)。先了解选题、分镜、Prompt、指标与审批的结构。
2. **主图与服务**：[graphs/main_graph.py](../backend/app/graphs/main_graph.py)、[graphs/service.py](../backend/app/graphs/service.py)。关注路由、返工上限、interrupt/resume、子图状态读取与 Fork。
3. **Agent 与 Skill**：[agents/base.py](../backend/app/agents/base.py)、[skills/registry.py](../backend/app/skills/registry.py)。Agent 负责模型调用，Skill 保存版本化业务指令；节点也可以是普通确定性函数。
4. **模型网关**：[integrations/llm.py](../backend/app/integrations/llm.py)。查看结构化解析、有限 Schema 修复、敏感字段脱敏、成功与失败调用记录。
5. **检索与运营接口**：[rag/hybrid.py](../backend/app/rag/hybrid.py)、[MCP Adapter](../mcp_server/app/adapters/wechat_workspace.py)。区分语义经验检索与精确数据查询，检查只读和路径白名单边界。
6. **存储与 Worker**：[repositories/postgres.py](../backend/app/repositories/postgres.py)、[workers/tasks.py](../backend/app/workers/tasks.py)。查看产物版本分配、指标去重和里程碑恢复。

## 几个值得追问的设计点

### 为什么不能让模型直接把流程跑到底？

创作者需要决定选题、修改分镜、确认视觉交付，发布和指标到达又是外部事件。显式状态机把暂停条件和恢复入口放在代码中，而不是依赖模型自行遵守对话约定。

### 历史结果如何知道用了哪版提示词？

初始化时保存 `skill_plan`，执行时记录版本和 Prompt hash。新版本通过新增目录和更新 manifest 发布，不覆盖历史版本。这里保证配置可追溯，不保证随机模型输出逐字复现。

### RAG 返回的数字能不能当概率？

不能。当前检索分数混合语义、词法、来源和时效，是排序信号。选题潜力和风险是模型判断，也不是校准概率。业务指标则由 MCP 精确读取，不混入语义相似度解释。

### 人工恢复会不会重复执行节点？

包含 `interrupt()` 的节点在恢复时会重新进入，再由 resume 值替代暂停返回值。因此要关注暂停前代码是否有副作用，不能假设“从函数暂停的下一行直接恢复”。

### 有了 checkpoint 和 Redis，是不是就生产可靠？

不是。当前 Graph 驱动仍有进程内任务边界，SSE 也使用进程内订阅队列；ARQ 负责指标轮询，不代表所有 Graph 执行都被持久调度。更完整的上线边界见[架构文档](architecture.md#运行边界)。

## 测试证据

| 验证方向 | 测试入口 |
| --- | --- |
| 审批、指标等待、分支与版本继承的工作流契约 | [工作流集成测试](../tests/integration/test_demo_workflow.py) |
| API 创建、读取与交互 | [API 测试](../tests/integration/test_api.py) |
| 检索排序与降级 | [RAG 单元测试](../tests/unit/test_rag.py) |
| Skill 版本和规则加载 | [Skill 测试](../tests/unit/test_skills.py) |
| 视觉交接与规则函数 | [视觉规则测试](../tests/unit/test_visual_rules.py) |
| 非法路径与未批准写回 | [写回边界测试](../tests/unit/test_writeback_guard.py) |
| 数据中心指标计算 | [运营数据测试](../tests/unit/test_content_data.py) |

规则函数有测试不表示它已经接入每条生产路径，尤其要区分视觉输入校验与尚未接入的视觉输出校验。上述测试也不能替代真实模型质量评测、历史预测回测或线上压测。
