# 架构说明

## 从大到小的嵌套关系

```mermaid
flowchart TB
    UI[React 工作台] --> API[FastAPI 异步 API]
    UI <-->|REST + SSE| API
    API --> WS[WorkflowService]
    WS --> G[LangGraph 主图]
    G --> SG1[选题子流程]
    G --> SG2[分镜子流程]
    G --> SG3[视觉 Prompt 子流程]
    G --> SG4[复盘子流程]
    SG1 --> A1[Strategy Agent]
    SG2 --> A2[Storyboard Agent]
    SG2 --> AR[Reviewer Agent]
    SG3 --> A3[Visual Agent]
    SG3 --> AR
    SG4 --> A4[Retro Agent]
    A1 --> S1[topic-strategy Skill]
    A2 --> S2[storyboard-design Skill]
    AR --> S3[content-review Skill]
    A3 --> S4[visual-prompt Skill]
    A4 --> S5[performance-retro Skill]
    G --> CP[(PostgreSQL Checkpoints)]
    API --> DB[(业务 PostgreSQL)]
    G --> RAG[分层 RAG]
    RAG --> V[(pgvector + FTS)]
    RAG --> EMB[DashScope Embedding]
    G --> MC[MCP Client]
    MC --> MCP[独立 WeChat MCP]
    MCP --> OPS[现有运营项目]
    W[ARQ Worker] --> MC
    W --> G
    W --> REDIS[(Redis)]
```

最外层是“产品”：前端、API、Worker 和 MCP 四个进程。API 内部包含工作流服务；工作流服务编译一张 LangGraph；Graph 的模型节点调用五个 Agent；每个 Agent 只加载自己的版本化 Skill。RAG 和 MCP 是 Graph 的工具层，不是 Agent。

## 一次创作如何串起来

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as React
    participant A as FastAPI
    participant G as LangGraph
    participant R as RAG/MCP
    participant L as Agents
    participant W as ARQ Worker

    U->>F: 输入灵感并启动
    F->>A: POST /projects/{id}/runs
    A->>G: 新 thread + 初始 state
    par 并行上下文
      G->>R: 长期/近期/案例 RAG
      G->>R: 精确运营指标
      G->>R: 相似文章
    end
    G->>L: Strategy Agent 生成 3 个候选
    G-->>F: interrupt.waiting(topic)
    U->>F: 选择/修改/自定义
    F->>G: Command(resume)
    G->>L: Storyboard -> Reviewer
    G-->>F: interrupt.waiting(storyboard)
    U->>F: 编辑并批准
    G->>L: Visual -> Reviewer
    G-->>F: interrupt.waiting(prompt)
    U->>F: 批准或单格重生成
    G-->>F: interrupt.waiting(publication)
    U->>F: 登记真实发布
    G-->>W: 等待 24h/48h
    W->>R: MCP 查询真实曲线
    W->>G: 达到里程碑后恢复
    G->>L: Retro Agent
    G-->>F: interrupt.waiting(knowledge)
    U->>F: 批准知识写回
    G->>R: 确定性节点调用受控 MCP Tool
```

## Agent 与确定性节点的边界

| 需要语言推理 | 确定性代码 |
|---|---|
| 三个选题的角度与叙事机制 | Excel/CSV 读取、指标计算 |
| 6–10 格故事设计 | Schema 和连续序号校验 |
| 英文视觉 Prompt | 路径白名单与幂等键 |
| 内容审核意见 | interrupt 判断、路由、重试次数 |
| 复盘解释和知识提案 | checkpoint、fork、批准后写回 |

设计原则：不是所有步骤都做成 Agent。可以稳定验证的工作使用普通代码，降低幻觉和成本。

## 状态、checkpoint 与时间回溯

`AgentState` 只保存 JSON 友好值。每个节点结束后 Checkpointer 保存状态和下一节点。历史产物带版本号；Skill 运行带 `skill_name/version/prompt_hash`。

Fork 的逻辑是：读取旧 `checkpoint_id` 的 `values + next`，复制为新 `thread_id`，应用用户 `state_patch`，从旧 `next` 继续。旧 thread 不修改，因此可以并排比较两条路线。

## RAG 与精确指标为什么分开

文章复盘、打法和叙事机制适合相似检索，所以进入 pgvector + 全文检索。阅读量、分享数和小时曲线必须精确，直接通过 MCP Tool 查询。把数字做向量相似度会丢失精确含义。

重排分数由语义、全文、来源等级和时效共同组成。Embedding 报错时，服务返回 `retrieval_degraded=true` 并改走全文检索，前端显示黄色提示。

## 写回安全

完整链路有四层门：前端人工批准、Graph 确定性审批节点、后端私密批准令牌、MCP 路径白名单与幂等存储。允许的目标只有：

- `drafts/<id>/article_record.md`
- `<周期>/weekly_review.md`
- `knowledge/content_playbook.md`

原始 Excel/CSV 没有任何写工具。
