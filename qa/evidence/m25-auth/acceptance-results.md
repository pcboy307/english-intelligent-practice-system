# M2.5 鉴权修正与换库验收

生成日期：2026-11-08

## Z1. 迁移可重建立

在一次性空库 `english_practice_z1_121202` 上按顺序执行：

```text
001_initial.sql
002_mistake_book.sql
```

结果：

```text
fresh database foreign keys = 33
current database foreign keys = 33
equal = true
```

- 新库清单：`fresh-db-foreign-keys.txt`
- 当前库清单：`current-db-foreign-keys.txt`
- 比对结果：`fresh-db-comparison.json`

## W3. 已删除 bank 的会话与报告残留

SQL 原文：`deleted-bank-residual-check.sql`

```text
orphan_sessions = 0
orphan_reports = 0
```

结论：无残留，不需要在历史列表中添加兼容说明。

## G. 换库

| 判据 | 实际输出 |
|---|---|
| G1 | 首页与覆盖统计均显示 `M2 Bank #2 · 共 300 题`，来源同为 `GET /stats/coverage` |
| G2 | 数据库存在 active / ready / archived；切换弹窗只列真实可切换库，当前项显示 `✓ 当前` 且 disabled |
| G3 | 归档库确认弹窗显示新旧库名称/题数、覆盖口径、错题迁移、历史报告、立即生效、取消，以及 `1` 个未完成练习提示 |
| G4 | 取消前后均为 `M2 Bank #2 / total=300` |
| G5 | `bank_switch_log` 有 M2→目标库、目标库→M2 两行，`operator=student_ui`，时间存在 |
| G6 | 切换后首页和覆盖统计均为 `M2.5 UI切换验收题库-258b1b · 共 5 题` |
| G7 | 切换后当前库错题 `0`；历史题库 `M2 Bank #2` 错题 `3` |
| G8 | 切换时 in_progress=1；切换后旧会话交卷成功，attempt 的 bank_id 为原 M2 |
| G9 | 无口令本地 activate 成功；外部 IP 返回 `403 ADMIN_LOCAL_ONLY` |
| G10 | A→B→A 后恢复 `M2 Bank #2 / total=300 / current mistakes=3` |

验收完成后已物理删除全部临时测试 bank。最终切换候选：

```text
M2 Bank #2  300题  active   current
```

最终列表截图：`bank-list-final.png`。
旧 `Demo Bank（30题·旧版演示）` 保留为 archived 且 `switchable=false`，
不出现在孩子可见的切换列表中。来源是原始 30 题 bootstrap 演示库。
旧 `Demo Bank（80题·归档）` 是 M1 历史演示库，供历史回看保留，但不面向孩子切换，
同样 `switchable=false`。因此最终可切换目标只有当前 M2 一个。

## P1. 外键

原始 `pg_constraint` 输出：`pg-constraints.txt`

```text
new-table foreign keys = 8
convalidated = true
orphan_attempts = 0
orphan_mistake_banks = 0
orphan_mistake_passages = 0
orphan_attempt_questions = 0
```

P1 修复时清理了 59 条指向不存在测试会话的 attempt 孤儿；未删除题库、报告或错题。

X1 的成因、提交范围与三层防复发：

`orphan-analysis.md`

## P2. 查询与写入路径

逐行审计：`query-write-audit.md`

```text
读路径命中数 = 12（安全 12 / 需修 0）
写路径命中数 = 18（安全 18 / 需修 0）
合计命中数 = 30
安全数 = 30
需修数 = 0
30 = 30 + 0
```

写路径分项：

```text
题库落库 = 5
扩库脚本 = 3
修题/迁移脚本 = 5
清理与运行时写入 = 5
写路径合计 = 18（安全 18 / 需修 0）
```

未发现 questions 按 `question_id/id` 单键 INSERT、UPDATE 或 DELETE。

## Y1. 复合键孤儿校验

SQL 原文：`orphan-checks.sql`

实际输出：`orphan-checks.txt`

```text
orphan_attempts = 0（session_id 对应 practice_sessions.id）
orphan_mistake_banks = 0（bank_id 对应 question_banks.id）
orphan_mistake_passages = 0（bank_id + passage_id 对应 passages）
orphan_attempt_questions = 0（bank_id + question_id 对应 questions(bank_id,id)）
```

写路径已经覆盖题库落库、扩库、修题/迁移、清理/运行时写入四类。
未发现 questions 按 `question_id/id` 单键 INSERT、UPDATE 或 DELETE。

## P3. 鉴权

实际测试：`auth-tests.txt`

```text
3 passed
maintenance 本地无口令 GET → 200
maintenance 外部 IP → 403 ADMIN_LOCAL_ONLY
activate 本地无口令 → 200
activate 外部 IP → 403 ADMIN_LOCAL_ONLY
bank_switch_log from/to/switched_at/operator 齐全
```

## S1. coverage tokens

`coverage-token-lines.txt`

```text
28:"coverage_repeat": "#2C5F5A"
29:"coverage_once": "#9A9A9A"
30:"coverage_none": "#E6E6E6"
```

## S2. Swagger

`openapi.txt`

```text
contracts/openapi.yaml is valid
```

## 前端弹窗

- 清空错题按钮位于错题本页头。
- 切换按钮紧邻题库名称，不再拉满到右侧。
- 两个清空弹窗均无口令输入框。
- 弹窗打开后先显示“请稍候…”，1.5 秒且实时条数返回后才启用“此操作不可恢复”。
- 取消后错题保持 `3 → 3`，覆盖保持 `297/2/1`。

## 回归

```text
pytest: 124 passed, 1 warning
M0_CHECK=PASS
API_CONTRACT_CHECK=PASS calls=20
OpenAPI: valid
TypeScript: tsc --noEmit
```

## X3 / Y3

- M2.5 签字文件：`M2.5-status.md`
- `work/` 已确认仅含本地 dump 与 tokenizer，不参与运行，已加入 `.gitignore` 并在
  `docs/交接说明.md` 说明。
