# Visual Prompt 版本与校验说明

[项目首页](../README.md) · [实际运行截图](business-workflow.md#视觉交付)

## 当前链路

分镜和视觉环节通过结构化交接卡传递角色、环境、时间、道具与叙事信息。当前代码的路径是：

```text
Storyboard Agent
  → 分镜审核（Reviewer；v1.1 结合确定性输入校验）
  → 人工编辑与批准
  → Visual Agent 生成结构化 Prompt 包
  → Pydantic 解析
  → 人工确认或局部重生成
```

需要区分三个层次：

- **已接入**：分镜交接卡补全、分镜输入规则校验、模型输出结构化解析、人工确认。
- **已有函数和测试，但未接入主图**：`validate_visual_prompts()` 对精确对白、固定画风、角色条款、封面裁切等输出的检查。
- **当前没有执行**：视觉 Prompt 生成后的独立 LLM Reviewer。主图将 `prompt_review` 置空并直接进入人工确认。

因此，Prompt 中写了约束不意味着代码已经强制保障全部约束。当前不能宣称视觉输出经过“确定性输出校验 + 独立 Reviewer”双重审核。

实现证据：[main_graph.py](../backend/app/graphs/main_graph.py)、[visual_rules.py](../backend/app/domain/visual_rules.py)、[相关测试](../tests/unit/test_visual_rules.py)。

## 版本化文件

v1.1 的业务规则保存在：

```text
backend/app/skills/visual-prompt/versions/1.1.0/
├── SKILL.md
├── prompt.md
├── rules.yaml
├── examples.yaml
└── evals/
```

修改画风、角色锚点或裁切条款时，应新增版本目录并更新 `manifest.yaml`，不覆盖历史版本。指令、Prompt 和规则共同参与 hash 计算。

## 历史运行为什么仍显示 v1.0.0？

新运行在初始化时冻结 `skill_plan`。人工重生成和 Fork 继承该计划，不会因为 manifest 更新而切换到新版本。缺少计划的旧 checkpoint 会结合已记录的版本作兼容处理。

[视觉结果截图](assets/screenshots/visual-prompts.png)与[调用记录截图](assets/screenshots/llm-traces.png)展示的是 v1.0.0 历史运行。其角色描述和文字处理应按该版本理解，不能作为 v1.1 品牌或精确对白规则生效的证据。

版本冻结让输入配置可追溯，不保证外部模型重复调用得到完全相同的输出。

## 正文与封面

- 正文画幅可在分镜审批中选择，视觉包按格组织内容与连续性说明。
- v1.1 规则要求封面无可绘制文字，并兼顾不同裁切比例；当前还需要人工核对实际输出。
- 参考图由创作者在外部绘图工具中准备，本项目不上传或保存这些附件，也不生成图片。

## 规则提示的含义

| 规则码 | 所在层与当前状态 |
| --- | --- |
| `brand-character-broken` | 分镜输入检查中的角色锚点问题 |
| `timeline-conflict` | 分镜输入检查中的时间信息冲突 |
| `dialogue-mismatch` | 视觉输出校验函数中的逐字对白检查，未接入主图 |
| `cover-crop-unsafe` | 视觉输出校验函数中的裁切条款检查，未接入主图 |
| `dialogue-too-long` | 长对白提示，不等于模型已自动修复文字 |

界面中的时间轴自检与提醒也不应被扩大理解为已经通过全部语义、品牌和视觉规则。
