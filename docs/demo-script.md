# 项目演示脚本（8–10 分钟）

## 1. 先讲问题（1 分钟）

“我原来运营微信公众号时，选题分镜和绘图 Prompt 是两个 Word Prompt，历史运营数据又在 Excel/Markdown。我把它们做成了一个有证据、有审批、有反馈闭环的 Agent，而不是单轮聊天机器人。”

## 2. 展示选题 Gate（2 分钟）

新建作品、输入灵感、启动。指出后台并行读取长期/近期/案例 RAG、精确指标和相似文章。展示三个候选在冲突与叙事机制上不同，以及右侧证据引用。选中一个继续。

可讲亮点：Embedding 失败会降级全文检索，界面明确提示，不会假装一切正常。

## 3. 展示分镜与 Reviewer（2 分钟）

修改一格对白或镜头，再批准。说明修改作为 state patch 进入 checkpoint；Reviewer 与创作 Agent 隔离，最多自动返工两轮，之后交给人。

## 4. 展示视觉 Prompt（1 分钟）

展示角色圣经、封面安全区、逐格英文 Prompt 和 continuity notes。点击单格重生成，强调其他格不覆盖；项目不生成图，控制 MVP 范围。

## 5. 展示时间回溯（1 分钟）

打开历史页，从选题或分镜 checkpoint Fork。说明新 thread 从旧节点继续，原路线保留；Skill 版本和 Prompt hash 也随状态记录。

## 6. 展示数据闭环和写回（2 分钟）

登记发布，点立即同步。说明 ARQ 每小时也会做同样的事；标题匹配不唯一会暂停。24h/48h 真实指标触发复盘，最后一次人工批准后 MCP 才写回单篇、周复盘或长期知识。

## 7. 收尾回答“为什么这么设计”（1 分钟）

- LangGraph：长期暂停、恢复、路由和 fork。
- Multi-Agent：按认知职责隔离 Strategy/Storyboard/Visual/Reviewer/Retro。
- Skill：业务知识版本化，不与 Python 节点耦合。
- RAG：给创作推理提供非结构化证据。
- MCP：隔离旧运营仓库，并给写回加安全边界。
- FastAPI/SSE/ARQ：让 Agent 成为可运行产品，而不是 Notebook。

## 可继续迭代

- 使用历史文章做离线评测与 A/B Prompt 版本比较。
- 接入 LangSmith/OpenTelemetry 做 token、成本和节点延迟观测。
- 增加图像模型，但仍放在 Prompt 审批之后。
- 从单用户扩展为多租户时，再加入身份、行级权限和密钥托管。
