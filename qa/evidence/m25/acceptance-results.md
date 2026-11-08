# M2.5 验收结果

生成日期：2026-11-08

## A. 错题本

| 判据 | 实际输出 | 复现证据 |
|---|---|---|
| A1 | `status=open, wrong_count=1, correct_streak=0` | `test_m25_wrong_answer_records_attempt_and_opens_mistake` |
| A2 | 第一次重做答对后 `correct_streak=1, status=open` | `test_m25_two_correct_reviews_master_then_wrong_reopens` |
| A3 | 第二次重做答对后 `correct_streak=2, status=mastered, mastered_at!=NULL`，待订正列表不再出现该题 | 同上 |
| A4 | 连续答对 1 次后重做答错，`correct_streak=0, status=open` | `test_m25_review_streak_rules[True]` |
| A5 | `mastered` 后答错，回到 `open`，`correct_streak=0, wrong_count=2` | `test_m25_two_correct_reviews_master_then_wrong_reopens` |
| A6 | 软删后 `sessions=1, reports=1, answers=1, attempts=1, mistakes=1, deletions=1`；报告接口返回 404 | `test_m25_report_delete_is_soft_and_preserves_learning_evidence` |
| A7 | 七选五键为 `seven:{passage_id}`，`wrong_count=1`；重做会话题目数 `5` | `test_m25_seven_mistake_is_one_passage_and_review_has_five_blanks` |
| A8 | 完形错 3 空产生 `3` 条错题；重做仅 `3` 题可作答，语篇共 `15` 题、`12` 题锁定 | `test_m25_cloze_keeps_three_items_and_review_limits_answerable_blanks` |
| A9 | 迁移连续执行 2 次成功；前后 `sessions` 与 `saved_answers` 计数不变 | `test_m25_migration_is_idempotent_and_preserves_existing_rows` |
| A10 | 学生 A 有错题，学生 B 无错题；B 的答题不改变 A 的状态 | `test_m25_mistake_state_is_isolated_by_student` |
| A11 | 空账号显示“暂时没有需要订正的题目” | `mistakes-empty.png` |

## B. 覆盖统计

| 判据 | 实际输出 | 复现证据 |
|---|---|---|
| B1 | `total=3, none=1, once=1, twice_plus=1` | `test_m25_coverage_counts_sessions_once_and_excludes_unsubmitted` |
| B2 | 同一会话对同一题保存两次后仍只计 1 个 session | 同上 |
| B3 | 未交卷会话不计入覆盖 | 同上 |
| B4 | practice + review 两会话计入 `twice_plus=1` | `test_m25_coverage_includes_mistake_review_sessions` |
| B5 | `1 + 1 + 1 = total = 3`；接口内有断言 | 同上 |
| B6 | 重置后显示“还没有开始练习”，无 `NaN` | `coverage-empty.png` |
| B7 | 三段颜色来自 `design-tokens` 的 `coverage_repeat/once/none` | `coverage-bar.png` |
| B8 | 显示 `M2 Bank #2 · 共 300 题` | `coverage-bar.png` |

## D. 换库刷新

| 判据 | 实际输出 | 复现证据 |
|---|---|---|
| D1 | 临时 Bank A `10` 题，Bank B `20` 题，其中 `5` 个 question_id 相同 | `test_m25_cross_bank_coverage_recomputes_from_shared_question_ids` |
| D2 | A 库做 5 题，覆盖为 `total=10, once=5, none=5, twice_plus=0` | 同上 |
| D3 | 切到 B 后为 `total=20, once=3, none=17, twice_plus=0` | 同上 |
| D4 | 共享题进入 current 组，仅旧库题进入 history 组 | `test_m25_bank_switch_regroups_current_and_historical_mistakes` |
| D5 | 切换前后 `question_attempts` 与 `mistake_items` 行数不变 | 上述两个换库测试 |
| D6 | A→B→A 后回到 `total=10, once=5, none=5` | `test_m25_cross_bank_coverage_recomputes_from_shared_question_ids` |
| D7 | 页面刷新后无旧数值、无 `NaN` | `coverage-bar.png`、`coverage-empty.png` |
| D8 | `bank_switch_log` 记录 `from_bank_id/to_bank_id/switched_at/operator=admin` | `test_m25_bank_switch_is_atomic_and_preserves_learning_state` |
| D9 | 切换前后 `question_attempts/mistake_items/error_tags/knowledge_mastery` 计数相等 | 同上 |

## E. 手工清空

| 判据 | 实际输出 | 复现证据 |
|---|---|---|
| E1 | 预览 `count=1, history_count=1`；确认后当前库 1→0，历史库 1→1 | `test_m25_clear_mistakes_only_affects_current_bank_and_student` |
| E2 | 浏览器点击取消后 `mistakes=4, coverage=297/2/1`，数据未变 | `browser-acceptance.json` |
| E3 | 当前库 attempts 删除 4 条，历史独有题 attempt 保留 1 条；覆盖回 `none=300` | `test_m25_reset_coverage_deletes_by_active_question_id_only` |
| E4 | 重置统计不改 `mistake_items`；清空错题不改 `question_attempts` | E1/E3 测试 |
| E5 | 预览 `4`，实际 `deleted_count=4`；清空预览 `3`，实际当前库 3→0 | E1/E3 与浏览器验收 |
| E6 | 再次点击返回 `deleted_count=0`；空状态无 `NaN` | E1/E3、`coverage-empty.png` |
| E7 | 第二次执行正常返回 0 | E1/E3 |
| E8 | 清学生 A 后，学生 B 的 `mistake_items=1` 不受影响 | E1 测试 |
| E9 | 清空前后 questions/passages/banks/practice_reports 计数不变 | E1 测试 |
| E10 | 四个 maintenance 接口无口令成功；非回环 403；activate 无口令成功且写日志；前端无口令框并保留1.5秒延迟 | `qa/evidence/m25-auth/acceptance-results.md` |

## F. 回归

| 判据 | 实际输出 |
|---|---|
| F1 | `121 passed, 1 warning` |
| F2 | `M0_CHECK=PASS` |
| F3 | `API_CONTRACT_CHECK=PASS calls=20` |
| F4 | `contracts/openapi.yaml is valid` |
| F5 | 本文件及 `browser-acceptance.json` |
