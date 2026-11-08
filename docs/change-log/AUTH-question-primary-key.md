# 补授权记录：questions 复合主键

- 日期：2026-11-08
- 授权来源：用户 M2.5 统一行动指引要求支持同一 `question_id` 跨库继承，
  并在后续 D1/D3 验收中使用两个 Bank 共享 5 个 `question_id`。
- 变更：`questions` 主键由 `(id)` 改为 `(bank_id, id)`。
- 原因：原全局唯一 id 使同一题号无法同时存在于新旧 Bank，覆盖统计与错题继承无法实现。
- 数据影响：不修改任何题目内容、不重写现有 `question_id`、不向 Bank #1 追加题目。
- 约束调整：
  - `session_items` 保留 `(bank_id, question_id)` 复合外键；
  - `error_tags` 改挂 `(bank_id, question_id)` 复合外键；
  - `question_attempts` 使用 `(bank_id, question_id)` 复合外键。
- 迁移：`db/migrations/002_mistake_book.sql`，可重复执行。
