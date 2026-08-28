# Visual Prompt Skill v1.1 学习说明

## 为什么不只修改一段 Prompt

大模型 Prompt 只能提高遵守规则的概率，不能保证中文字和标点逐字正确。因此 v1.1 分为三层：

```text
Storyboard Agent
  → 结构化分镜 + handoff_card
  → Python 确定性输入校验
  → Visual Agent 生成结构化 Prompt 包
  → Python 确定性输出校验
  → 独立 LLM Reviewer
  → 人工审批
```

- Agent 负责需要理解剧情的部分，例如构图、情绪和动作降维。
- Pydantic 负责字段、类型和格数结构。
- `visual_rules.py` 负责逐字对白、品牌角色、固定条款和裁切规则。
- 人工审批处理模型仍无法可靠判断的审美与例外。

## 修改提示词的位置

不要覆盖 `1.0.0`。当前版本位于：

```text
backend/app/skills/visual-prompt/versions/1.1.0/
├── SKILL.md       角色、职责和不可越过的边界
├── prompt.md      模型执行步骤与 Prompt 拼装顺序
├── rules.yaml     可被代码校验的固定常量
├── examples.yaml  正例与反例
└── evals/         Agent 评测案例
```

需要改变固定画风、裁切百分比、角色英文锚点或气泡样式时，复制为 `1.2.0` 后修改 `rules.yaml`，再更新 `manifest.yaml`。普通措辞优化修改新版本的 `prompt.md`。

## Skill 版本如何冻结

新运行在 `initialize` 节点把全部 Skill 当前版本写入 `skill_plan`。后续自动返工、人工重生成、服务重启和 fork 都读取该计划，不会因为 manifest 更新而切换版本。

已有 checkpoint 没有 `skill_plan` 时，工作流优先读取已记录的 `skill_versions`；发现旧运行使用 `1.0.0` 后，其余尚未执行的 Skill 也沿用 `1.0.0`。因此升级不会改变历史路线。

## 正文与封面差异

- 正文默认 4:3，可以在分镜审批页改为 1:1；中文对白直接进入图片 Prompt。
- 封面固定 16:9，无任何文字，同时兼容中心 1:1 与 2.35:1 裁切。
- 参考图只显示准备顺序，不上传、不保存；复制 Prompt 到 Nano Banana 2 后手动添加附件。

## 常见 Reviewer 提示

- `brand-character-broken`：一二或布布被改成人类，点击“应用固定品牌锚点”。
- `dialogue-mismatch`：Prompt 与分镜精确中文不同，包括漏标点。
- `dialogue-too-long`：单泡超过 12 字，只提醒，不阻止人工批准。
- `timeline-conflict`：逐格时间与交接卡不一致，回到分镜卡修改。
- `cover-crop-unsafe`：封面缺少中央安全区或双裁切完整条款。
