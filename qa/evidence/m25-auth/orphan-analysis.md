# X1：59 条孤儿 attempt 成因与防复发

## a) `session_id` 外键

当前存在：

```text
question_attempts_session_fk
FOREIGN KEY (session_id) REFERENCES practice_sessions(id) ON DELETE RESTRICT
convalidated=true
```

59 条发生在约束加入之前。可复查的提交历史：

```text
e66cb42 创建 question_attempts，原始 DDL 只有 NOT NULL，没有 session/bank/question 外键
bd3ca41 开始写 question_attempts，但 delete_report 仍物理删除 sessions
1a3c316 才把 delete_report 改为软删除
```

因此这 59 条不是“有外键却写入成功”，而是旧测试流程在无外键时执行了：

```text
submit -> 写 attempt -> 旧 delete_report 物理删除 session
```

对应旧代码可从以下命令复查：

```powershell
git show e66cb42:db/migrations/002_mistake_book.sql
git show bd3ca41:backend/app/pg_store.py
```

## b) 题目外键

当前存在复合外键：

```text
FOREIGN KEY (bank_id, question_id)
REFERENCES questions(bank_id, id)
ON DELETE RESTRICT
```

不是只引用 `question_id` 单列。

## c) 59 条来源

2026-11-08 清理时实际删除的 59 个 id 为：

```text
65..93
359..375
376
377..388
```

来源均为本地 pytest/浏览器验收通过 API 交卷生成的测试会话；随后由 Stage 2 时仍存在的
硬删除 `delete_report` 路径删除。没有生产用户数据或真实学习记录被清理。

## d) 防复发

当前防复发有三层：

1. `question_attempts_session_fk` 阻止写入不存在 session。
2. `question_attempts_question_bank_fk` 阻止写错 bank 的 question。
3. `question_attempts_bank_fk` 阻止不存在 bank。

行为测试 `test_m25_attempt_foreign_keys_reject_orphans_and_wrong_bank` 已证明：

- 伪造 session_id 写入被拒；
- 使用存在 session 但错误 bank/question 组合写入被拒；
- 删除仍有 attempt 引用的 session 被拒。

可能的未来写入路径只剩 `record_session_results`；它从已提交会话读取
`student_id/session_id/bank_id`，并与 attempt 写入在同一事务中。放弃中的会话不会写 attempt。
任何测试清理脚本必须先删除 attempts，再删除 session；数据库现在会强制这个顺序。
