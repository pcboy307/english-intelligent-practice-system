# CO-005 修正：报告软删

- 日期：2026-11-08
- 修正范围：历史报告删除语义

## 原偏差

原 `backend/app/pg_store.py:622-654` 的 `delete_report` 实际执行物理删除：

```text
error_tag_successes
practice_reports
saved_answers
session_items
practice_sessions
```

因此 CO-005 原文所称的“报告软删”从未实现。

## 本次修正

- 删除报告时只向 `report_deletions` 写入
  `(session_id, student_id, deleted_at)`。
- `practice_reports`、`practice_sessions`、`saved_answers`、
  `session_items`、`question_attempts`、`mistake_items` 全部保留。
- 历史列表与报告读取接口通过 `NOT EXISTS report_deletions` 过滤。
- 重复删除保持幂等，不改变首次删除时间。

## 不可恢复说明

修正前已有 150 个会话没有报告（743 会话、593 报告）。这些会话的关联数据在旧实现中
已经被物理删除，本次无法恢复。

本次不回填 743 次历史会话或 15413 条历史作答，原因是这些记录均为调试与验收数据，
不是学生真实学习数据。
