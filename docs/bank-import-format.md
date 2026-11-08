# 题库导入格式

首页点“切换”，在题库弹窗右上角点“导入题库”，选择一个 UTF-8 JSON 文件。
预览只做结构和题库闸门校验；确认导入时默认再调用 `deepseek-v4-pro` 独立审题。
任一步失败均不落库。成功后新库立即成为当前题库，原当前题库转为历史归档。

正式全量库使用 `m26-v1`，必须恰好为 72 篇 / 500 题：

- 完形 12 篇 × 15 题
- 语法填空 12 篇 × 10 题
- 阅读 40 篇 × 4 题
- 七选五 8 篇 × 5 题
- 难度 60 / 120 / 190 / 95 / 35
- 册次 113 / 75 / 50 / 12

小型测试包可使用 `bank-v1`，题量和篇数由包内 `target_size` 与
`composition` 自行保持一致。

## 顶层结构

```json
{
  "format_version": "bank-v1",
  "name": "示例题库",
  "target_size": 4,
  "difficulty_profile": "advanced",
  "generated_at": "2026-11-08",
  "composition": {
    "cloze": 0,
    "grammar_fill": 0,
    "reading": 1,
    "gap_fill": 0
  },
  "passages": []
}
```

每篇至少包含：

```json
{
  "type": "reading",
  "passage_group_id": "EXAMPLE-READING-01",
  "topic": "科技",
  "book_source": "选必2",
  "difficulty": 3,
  "passage": "Full passage text.",
  "questions": []
}
```

每题必须包含连续编号、答案、中文解析和至少一个语法标签。阅读题还必须包含
`stem` 与可在 `passage` 中精确找到的 `evidence_sentence`。

七选五使用篇级共享选项，五题只写 `number / answer / explanation /
grammar_tags`：

```json
{
  "type": "gap_fill",
  "options": {
    "A": "First sentence.",
    "B": "Second sentence.",
    "C": "Third sentence.",
    "D": "Fourth sentence.",
    "E": "Fifth sentence.",
    "F": "Sixth sentence.",
    "G": "Seventh sentence."
  }
}
```

完整机器契约见 `contracts/schemas/bank-import-package.json`。导入器还会重新计算
词数、Flesch、占位符、答案泄漏、词汇范围和题型结构，不采信文件内的自评结论。

## 删除题库

每个非当前题库行都有“删除”按钮。删除前显示实际篇数、题数、会话、报告、作答记录
和错题数，并等待 1.5 秒后才允许确认。删除是永久物理删除，同时清除该题库的全部关联
历史数据；当前题库不可删除，生成任务运行中的题库也不可删除。

导入与删除接口只接受 `127.0.0.1 / ::1` 回环来源，不要求本地口令。
