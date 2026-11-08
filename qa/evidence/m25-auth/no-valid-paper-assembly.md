# NO_VALID_PAPER_ASSEMBLY 修复记录

日期：2026-11-08

## 复现

学生：

```text
30c115c0-c3c4-4859-b6eb-a4a114c458f2
```

该学生有 5 个 `in_progress` 会话，均早已超过 `deadline`：

```text
Demo Bank  2026-11-07 11:21:49 -> 11:51:49
Demo Bank  2026-11-07 21:51:20 -> 22:21:20
M2 Bank #2 2026-11-08 10:21:18 -> 10:51:18
M2 Bank #2 2026-11-08 11:14:25 -> 11:44:25
M2 Bank #2 2026-11-08 11:14:35 -> 11:44:35
```

修复前真实 API：

```text
POST /api/v1/practice/start
HTTP 400
{"detail":{"code":"NO_VALID_PAPER_ASSEMBLY"}}
```

组卷器输入中的过期占用：

```text
M2-FULL-CLOZE-02
M2-FULL-GAP-01
M2-FULL-GRAMMAR-05
```

## 根因

`_student_state` 的并发语篇查询只判断：

```sql
status='in_progress'
```

没有判断：

```sql
deadline > now()
```

因此过期会话永久占用 passages，最终没有任何完整骨架或题级 fallback 候选。

## 修复

- `_student_state` 只把 `deadline > now()` 的会话计为并发占用。
- 换库弹窗的未完成会话数同样只统计未过期会话。

## 回归

- 新增 `test_start_practice_ignores_expired_in_progress_sessions`
- 同一学生复测：`HTTP 201`，正常生成 30 题
- 全量：`124 passed, 1 warning`
