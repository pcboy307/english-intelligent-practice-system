# 提示词模板库

本目录保存项目可复用的提示词模板，不替代 `contracts/` 和 `docs/question-bank-generation-standard-v2.md`。使用顺序：

1. 先读 `docs/question-bank-generation-standard-v2.md`。
2. 确认 JSON Schema、当前版本、配额和题库状态。
3. 选择对应模板。
4. 将模板中的 `{{placeholder}}` 替换为真实输入。
5. 用确定性校验器复核模型输出。

模板：

- [生成单篇题库内容](generate-bank-passage.md)
- [评审题库或修订包](review-bank.md)
- [生成薄弱知识点分析](weakness-analysis.md)
- [裁定需求变更](change-adjudication.md)

## 通用原则

- 输出模式先声明：生成、只评审、修改后输出完整 JSON。
- 不让模型自己计算可信配额，配额由脚本注入并复核。
- 一次只生成一个可验证单元。
- 先给 Schema 和错误码，再给内容任务。
- 不把“机器校验通过”写成“内容正确”。
- 不把题级标签、教材来源和解析当成可以为了过校验而倒填的字段。
- 所有失败样本保留失败类别和原始响应。

## 项目 Skill

可加载的项目专用 Skill：

```text
skills/high-school-english-content-ops/SKILL.md
```

它负责在生成、评审、修复和发布之间路由，并引用本目录模板。
