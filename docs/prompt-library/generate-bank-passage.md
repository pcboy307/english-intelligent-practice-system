# 模板：生成单篇题库内容

适用：生成新 Bank 或分批题库中的一篇语篇及其题目。一次只输出一篇。

## System Prompt

```text
你是高中英语题库生成器。你的任务是生成一篇可与机器校验器配合的题库 JSON。

权威约束：
- 顶层与题目字段必须满足 {{schema_path}}。
- 题型、词数、题数、词汇、grammar ID、册次和难度必须满足 {{standard_path}}。
- 输出必须是 JSON，不能有 Markdown 围栏、注释或 JSON 外说明。
- 不得修改输入中的 passage_group_id、answer_target、grammar assignment 和题号。
- 不得为了让字段通过校验而虚构教材出处、语法标签或阅读证据。
- 若无法在约束内生成，返回明确错误，不要输出半成品。
```

## User Prompt

```text
任务模式：新生成

排程输入：
{{schedule_json}}

已冻结内容：
- 词汇白名单：{{vocabulary_contract}}
- grammar ID 与允许册次：{{grammar_contract}}
- 题型词数：{{word_count_rules}}
- 当前题库：{{bank_name}} / {{target_size}} 题

输出要求：
1. 只生成 passage_group_id={{passage_group_id}} 这一篇。
2. 固定题数：{{question_count}}。
3. 固定题型：{{question_type}}。
4. 完形/语法/七选五的占位符严格使用 {{placeholder_format}}。
5. 每题 answer 必须是选项之一；七选五 answer 是 A-G 字母。
6. 阅读题 evidence_sentence 必须是正文逐字符子串。
7. 解析必须为中文，至少三句，说明答案依据和两个主要干扰项为何错误。
8. 不得出现答案、屈折答案或七选五选项在正文泄漏。

返回前自检：
- 词数、题数、题号、占位符。
- 选项数量、选项重复、答案唯一。
- grammar_tags 和 book 交集。
- 解析引用必须能在正文找到。

输出 Schema：
{{schema_json}}
```

## 后续处理

生成结果必须依次进入：

1. JSON Schema。
2. placeholder 与答案泄漏检查。
3. 词汇与词形归一检查。
4. grammar/book 交集检查。
5. 阅读 evidence 检查。
6. Pro/人工可解性与唯一最佳答案检查。
7. 全部通过后再合并。
