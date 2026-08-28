# Bubu ContentOps Agent 协作约定

## 业务资料读取顺序

涉及选题、标题、预测或复盘时，通过 MCP 按以下优先级读取：

1. 最近周复盘；
2. 最近已复盘的 `drafts/*/article_record.md`；
3. 长期 `knowledge/content_playbook.md`；
4. 精确指标与当前文章详情。

近期变化用于调整判断，长期知识只能在多篇重复验证后升级。

## 边界

- Agent 只做需要模型推理的工作；检索、计算、Schema 校验、审批和写回使用确定性节点。
- 原始 Excel/CSV 只读。
- 没有人工批准时，禁止写回 Markdown。
- 修改 Skill 时新增版本目录，禁止覆盖历史版本。
- 所有外部调用异步执行；阻塞文件读取放入线程池。
- 新增 Graph 节点时必须补正常路由、失败恢复和 interrupt/resume 测试。

