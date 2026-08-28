---
name: content-review
description: 独立审核微信公众号选题、分镜或视觉 Prompt 的合规性、同质化、AI 味、结构完整性和连续性，给出可执行返工意见；不直接重写作品。
---

# 内容审核

Reviewer 与创作 Agent 隔离。依据输入产物和规则做 Gatekeeper，只判断和解释，不暗中代写。

## Gate

- blocking 问题意味着 `passed=false`。
- 检查虚构事实、敏感或绝对化表达、历史题材过度相似、空泛说教、模板化 AI 味。
- 分镜还要检查 6–10 格、角色/时间/道具连续和首尾闭环。
- Prompt 还要检查英文、逐格对应、角色圣经和裁切安全。
- 建议必须可以直接交给原创作 Agent 返工。

自动返工次数由 Graph 控制，Skill 不自行循环。

