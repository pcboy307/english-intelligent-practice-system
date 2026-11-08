# 题库导入导出格式

状态：V1 标准。

大模型生成、评审和修改题库时必须先阅读：

```text
docs/question-bank-generation-standard-v2.md
```

数据库导出的文件和手工准备、供导入的文件使用同一份 JSON Schema：

```text
contracts/schemas/bank-import-package.json
```

## 顶层字段

```json
{
  "format_version": "bank-v1",
  "name": "M2 Bank #2",
  "target_size": 300,
  "difficulty_profile": "standard",
  "generated_at": "2026-11-08T12:00:00+08:00",
  "composition": {
    "cloze": 6,
    "grammar_fill": 6,
    "reading": 25,
    "gap_fill": 10
  },
  "passages": []
}
```

- `target_size` 是文件中实际题目总数。
- `composition` 是每种题型的实际语篇数。
- 导入后 Bank 会获得新的 `bank_id`，并由系统自动设为 active。
- Bank 名称必须全局唯一；重新导入同一名称前需修改 `name`。
- 新生成文件使用 `validation_profile: "m2"` 或 `"m26"`；`stored` 只用于系统导出。
- 修改导出题库后，必须把修改篇改回 `m26`，并更新名称、时间、题数和篇数。

## 导出特点

数据库导出固定使用：

```json
{
  "format_version": "bank-v1"
}
```

每个导出语篇携带：

```json
{
  "validation_profile": "stored"
}
```

`stored` 表示数据已经来自数据库。重新导入时仍执行：

- JSON 结构和字段校验；
- 语篇与题目数量校验；
- 选项数量与答案校验；
- 册次、册次标签和 grammar 字段结构校验；
- 名称唯一性与事务写入。

不会重复执行只适用于新生成内容的占位符、阅读证据和生成提示词质量门禁。

导出文件用于大模型评审或修改时，完整规则见
`docs/question-bank-generation-standard-v2.md`。只评审不应修改 JSON；
修改并重新导入时必须输出完整 JSON。

## 导入接口

```text
POST /api/v1/banks/import/preview
POST /api/v1/banks/import
```

## 导出接口

```text
GET /api/v1/banks/{bank_id}/export
```

导出接口和导入接口均只接受本机回环来源。页面中的每个 Bank 行在“删除”左侧提供“导出”按钮。
