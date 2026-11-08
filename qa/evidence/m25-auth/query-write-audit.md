# M2.5 查询与写入路径审计

范围：错题本、覆盖统计、软删、题库落库、扩库、修题、迁移、清理
和题库切换的直接持久化路径。

## 读路径

读路径命中数 = 12（安全 12 / 需修 0）

| ID | 文件:行 | 路径 | 判定 |
|---|---|---|---|
| R01 | `backend/app/mistakes.py:146` | 读取 active bank | 安全：active_bank_id |
| R02 | `backend/app/mistakes.py:152` | 读取 active question_id | 安全：bank_id |
| R03 | `backend/app/mistakes.py:163` | 读取 active passage_id | 安全：bank_id |
| R04 | `backend/app/mistakes.py:172` | 读取 open mistakes | 安全：`student_id` |
| R05 | `backend/app/mistakes.py:185` | 读取题库名称 | 安全：只读 |
| R06 | `backend/app/mistakes.py:262` | 读取语篇错题 | 安全：`student_id + passage_id` |
| R07 | `backend/app/mistakes.py:289` | 读取语篇 | 安全：`bank_id + passage_id` |
| R08 | `backend/app/mistakes.py:301` | 读取题目 | 安全：`bank_id + passage_id` |
| R09 | `backend/app/mistakes.py:422` | 聚合覆盖次数 | 安全：`student_id + active question_ids` |
| R10 | `backend/app/mistakes.py:462` | 清空预览计数 | 安全：`student_id + bank_id` |
| R11 | `backend/app/mistakes.py:530` | 重置预览计数 | 安全：`student_id + active question_ids` |
| R12 | `backend/app/mistakes.py:572/584` | 可切换题库与未完成会话数 | 安全：全部题库按产品要求读取；会话按 `student_id + active bank` |

## 写路径

写路径命中数 = 18（安全 18 / 需修 0）

### 题库落库

| ID | 文件:行 | 路径 | 判定 |
|---|---|---|---|
| W01 | `backend/app/m2_repository.py:55` | 新建 question_banks | 安全：UUID 主键 |
| W02 | `backend/app/m2_repository.py:195` | 写 passages | 安全：`bank_id + passage_group_id` |
| W03 | `backend/app/m2_repository.py:216` | 写 questions | 安全：`bank_id + id` |
| W04 | `backend/app/pg_store.py:123` | 更新 seed passages | 安全：`bank_id + passage_group_id` |
| W05 | `backend/app/pg_store.py:140` | 更新 seed questions | 安全：`bank_id + id` |

### 扩库脚本

| ID | 文件:行 | 路径 | 判定 |
|---|---|---|---|
| W06 | `backend/app/m2_repository.py:115` | 创建 generation_jobs | 安全：job UUID |
| W07 | `scripts/run-m2-full.py:865` | 扩库前删除本 bank questions | 安全：整库按 `bank_id` 替换 |
| W08 | `scripts/run-m2-full.py:869` | 扩库前删除本 bank passages | 安全：整库按 `bank_id` 替换 |

### 修题/迁移脚本

| ID | 文件:行 | 路径 | 判定 |
|---|---|---|---|
| W09 | `backend/app/m2_repository.py:268` | 修复 passages | 安全：`bank_id + passage_group_id` |
| W10 | `backend/app/m2_repository.py:287` | 修复 questions | 安全：`bank_id + passage_group_id + id` |
| W11 | `scripts/finalize-m2-gap-repairs.py:93` | 发布修复题 | 安全：`bank_id + passage_group_id + batch_id` |
| W12 | `db/migrations/002_mistake_book.sql:187` | questions 复合主键 | 安全：`(bank_id, id)` |
| W13 | `db/migrations/002_mistake_book.sql:201` | error_tags 复合外键 | 安全：`(bank_id, question_id)` |

### 清理与运行时写入

| ID | 文件:行 | 路径 | 判定 |
|---|---|---|---|
| W14 | `backend/app/mistakes.py:53` | 写 question_attempts | 安全：session 所属 student/bank |
| W15 | `backend/app/mistakes.py:87` | upsert mistake_items 答错态 | 安全：student/bank/question |
| W16 | `backend/app/mistakes.py:123` | 更新连续答对状态 | 安全：student/bank/question |
| W17 | `backend/app/mistakes.py:487` | 清空当前题库错题 | 安全：`student_id + active bank` |
| W18 | `backend/app/mistakes.py:557` | 重置当前题号 attempts | 安全：`student_id + active question_ids` |

## 单键写检查

```text
questions 的 INSERT：同时提供 bank_id + id
questions 的 UPDATE：使用 bank_id + passage_group_id + id
questions 的 DELETE：使用 bank_id 整库替换
未发现按 question_id/id 单键 INSERT、UPDATE 或 DELETE questions 的位置
```

`practice_sessions`、`error_tags`、`generation_jobs` 等按自身 UUID 主键更新，
不属于跨库 question_id 单键写路径。

## 总数核对

```text
读路径命中数 = 12（安全 12 / 需修 0）
写路径命中数 = 18（安全 18 / 需修 0）
合计命中数 = 30
安全数 = 30
需修数 = 0
30 = 30 + 0
```
