# M2.5 查询与写入路径审计

范围：错题本、覆盖统计、软删、手工清空、题库切换新增或修改的直接持久化路径。

判定口径：

- 学生数据路径必须包含 `student_id` 或由已归属学生的 session 派生。
- 题库数据路径必须绑定 active bank 或请求指定的 bank。
- 全局题库切换只允许本机回环来源，并在事务内更新 active 状态和写日志。

## 读取路径

| ID | 文件:行 | 操作 | 判定 |
|---|---|---|---|
| R01 | `backend/app/mistakes.py:146` | 读取 active bank 名称 | 安全：active_bank_id |
| R02 | `backend/app/mistakes.py:152` | 读取 active bank question_id | 安全：bank_id |
| R03 | `backend/app/mistakes.py:163` | 读取 active bank passage_id | 安全：bank_id |
| R04 | `backend/app/mistakes.py:172` | 读取 open mistake_items | 安全：`student_id` |
| R05 | `backend/app/mistakes.py:185` | 读取题库名称映射 | 安全：只读名称 |
| R06 | `backend/app/mistakes.py:262` | 读取指定语篇错题 | 安全：`student_id + passage_id` |
| R07 | `backend/app/mistakes.py:275` | 检查 active bank 是否有该语篇 | 安全：active bank |
| R08 | `backend/app/mistakes.py:289` | 读取语篇与题数信息 | 安全：`bank_id + passage_id` |
| R09 | `backend/app/mistakes.py:301` | 读取语篇题目 | 安全：`bank_id + passage_id` |
| R10 | `backend/app/mistakes.py:403` | 读取 coverage active bank | 安全：active bank |
| R11 | `backend/app/mistakes.py:411` | 读取 coverage active question_id | 安全：bank_id |
| R12 | `backend/app/mistakes.py:422` | 聚合 attempt 覆盖次数 | 安全：`student_id + active question_ids` |
| R13 | `backend/app/mistakes.py:456` | 读取清空预览题库 | 安全：active bank |
| R14 | `backend/app/mistakes.py:462` | 统计当前/历史错题 | 安全：`student_id + bank_id` |
| R15 | `backend/app/mistakes.py:520` | 读取重置预览题库 | 安全：active bank |
| R16 | `backend/app/mistakes.py:530` | 统计待删除 attempts | 安全：`student_id + active question_ids` |
| R17 | `backend/app/mistakes.py:572` | 列出可切换题库 | 安全：产品要求列出全部库 |
| R18 | `backend/app/mistakes.py:584` | 统计当前学生未完成会话 | 安全：`student_id + active bank` |

## 写入路径

| ID | 文件:行 | 操作 | 判定 |
|---|---|---|---|
| W01 | `backend/app/mistakes.py:51` | 写 `question_attempts` | 安全：session 所属 student/bank |
| W02 | `backend/app/mistakes.py:85` | upsert `mistake_items` 答错态 | 安全：session 所属 student/bank |
| W03 | `backend/app/mistakes.py:121` | 更新连续答对状态 | 安全：session 所属 student/bank |
| W04 | `backend/app/mistakes.py:485` | 清空当前题库错题 | 安全：`student_id + active bank` |
| W05 | `backend/app/mistakes.py:555` | 重置当前题号 attempts | 安全：`student_id + active question_ids` |
| W06 | `backend/app/pg_store.py:367` | 旧 active bank 转 archived | 安全：回环 + 事务 |
| W07 | `backend/app/pg_store.py:375` | 新 bank 转 active | 安全：回环 + 事务 |
| W08 | `backend/app/pg_store.py:383` | 更新 `bank_active_state` | 安全：回环 + 事务 + 触发器 |
| W09 | `backend/app/pg_store.py:391` | 写 `bank_switch_log` | 安全：记录 from/to/time/operator |
| W10 | `backend/app/pg_store.py:678` | 创建 review session | 安全：目标来自学生错题 |
| W11 | `backend/app/pg_store.py:698` | 写 review session_items | 安全：使用 review session 的 bank |
| W12 | `backend/app/pg_store.py:912` | 写 `report_deletions` | 安全：`student_id + session_id` 已先校验 |

## 核对

```text
命中位置总数 = 30
安全数 = 30
需修数 = 0
30 = 30 + 0
```
