# CO-005 交付说明

状态：实现完成，等待所有者验收。

## 已实现

- 练习页每次只显示一道题，右上角统一放上一题、下一题、查看报告和交卷按钮。
- 报告页“查看原题”位于每道解析区域的右上角。
- 薄弱知识点使用本地 `qwen-local` 分析，最多返回 100 字中文建议。
- 报告页删除旧的规则标签三行，仅保留模型分析。
- 历史报告使用标题 `日期-时间-题目数-分数`，支持打开和二次确认删除。
- 历史题目与作答只通过“历史报告 → 打开 → 查看原题”访问，不提供独立题目历史入口。
- 删除报告时使用单一事务同步删除 `practice_reports`、`saved_answers`、`session_items` 和 `practice_sessions`。

## 证据

- `scripts/check-co005.py`：模型分析来源 `llm`，长度不超过 100；历史列表可打开；删除后四张关联表计数为 0。
- `qa/evidence/co005-single-question.png`
- `qa/evidence/co005-history-list.png`
- `qa/evidence/co005-history-report.png`

最近一次本地模型分析为 `83` 字，来源为 `llm`；删除测试中
`practice_reports=0`、`saved_answers=0`、`session_items=0`、`practice_sessions=0`。

## 浏览器确认

- 每次只显示一道题，右上角固定显示上一题、下一题、查看报告和末题的“交卷”。
- 历史报告只能从列表打开，题目详情只能继续从报告中的“查看原题”进入。
- 报告页每道解析的状态行右侧都有“查看原题”按钮。
- 报告页不再显示三行旧的 `knowledge_point：答案选择` 标签，只保留模型生成的中文分析。
