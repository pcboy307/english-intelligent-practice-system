# Bank 模型契约

状态：M0 冻结点。本文与 `contracts/schemas/bank.json`、`contracts/openapi.yaml` 和迁移共同定义 Bank 语义。

## 1. 核心定义

- 一次生成 job 只生成一个完整 Bank。
- Bank 是题目、语篇、生成批次、审核记录和 Coverage 快照的隔离边界。
- `questions.bank_id` 与 `passages.bank_id` 必填。
- 题目 ID 全局唯一；题目和语篇同时通过 `(id, bank_id)` 复合外键约束保证不跨 Bank 关联。
- 不存在“向已有 Bank 追加题目”的 API、UI 或服务方法。

## 2. 生命周期

```text
draft -> generating -> reviewing -> ready -> active
                                  \<- ready
                                      \-> archived
active -> archived
```

- `draft`：Bank 已创建，尚无运行中的 job。
- `generating`：有且只有一个运行中的 generation job。
- `reviewing`：自动校验完成，等待人工审核。
- `ready`：审核完成且可作为待激活候选。
- `active`：当前生效 Bank，新会话使用。
- `archived`：不再作为激活候选，但所有历史数据保留。
- 切换生效 Bank 时，旧 active Bank 回到 `ready`，不是 `archived`。
- `active → ready` 只用于原子切换；切换事务必须同时记录审计。
- 任一时刻最多一个 `active` Bank，由 PostgreSQL 部分唯一索引保证。
- 禁止物理删除 Bank；默认不提供物理删除接口。

## 3. 创建与生成

- 创建 Bank 时记录 `name`、`target_size`、`difficulty_profile`、`status=draft`。
- 生成前必须由系统所有者单独批准，并先通过 `/admin/banks/{id}/approve-generation` 写入服务端审批记录；生成请求不接受客户端布尔批准。
- 每个 generation job 固定绑定 `bank_id`，job 中途不得更换。
- 单批最多 10 篇语篇。
- 首批完成后状态变为 `paused_for_review`，不得继续下一批，直到人工确认。
- 失败批次可重试；已 ready 的 Bank 不受影响；续跑只重做失败批次。
- 每次生成、拒收、审核和状态变化写审计记录。

## 4. 生效与切换

- 切换使用事务：锁定目标 Bank 行，将旧 active Bank 改为 `ready`，目标 Bank 改为 `active`，并写 `bank_audit_logs`。
- 审计必记：操作时间、切换前 Bank ID、切换后 Bank ID、操作者标识。
- 新会话创建时快照 `bank_id`、`bank_name`、`bank_version`。
- 已开始会话、历史报告、错题记录永久保留原 `bank_id`，切换不得回写。
- App 仅只读显示当前 active Bank 名称，不提供切换入口。

## 5. 组卷隔离

- 组卷候选集为 `WHERE bank_id = session.bank_id AND status = 'published'`。
- 禁止跨 Bank 混抽，即使题目知识点相同。
- 每套卷只选 1 篇完形、1 篇语法填空、1 篇阅读或七选五。
- 选题只执行两条规则：先选择三篇覆盖次数总和最少的组合；总和并列时，
  优先选择覆盖 3 个不同话题的组合。
- 语篇覆盖次数按本学生在已交卷或已过期会话中出现的次数去重计算，不按题数重复累计。
- 已交卷或已过期会话中的语篇计为已覆盖；主动退出的会话不计。
- 册次、难度、grammar tag 重复、知识点重复、错题池占比和历史权重均不参与选题。
- Bank 切换只改变之后创建的新会话。

## 6. 错误标签与跨 Bank 语义

主动错题标签以 `device_student_id + question_id + bank_id` 为唯一业务身份，并快照 `knowledge_points` 与 `grammar_tags`。

- `I_err`：只有标签所属 `bank_id` 等于 session Bank 时才计入该 Bank 的错题状态。
- `S_kp`：按知识点/语法标签跨 Bank 统计活跃错题，最多计 3。
- `G_gap`：知识点掌握度跨 Bank 记录，基于 `knowledge_mastery`，用于报告和学习状态。
- `streak`：按错误标签所属 Bank 独立冻结和续算；换库不增加、不重置。
- 两次不同会话都答对后转 `mastered`；同套内重复只取该题第一次结果。
- `mastered` 后再次答错，转回 `active` 且 `streak=0`。
- 上述错题和掌握度字段用于学习状态与报告，不参与新练习的最终选题排序。
- 新练习选题不读取上述错题和掌握度字段。

## 7. Coverage 与选库

Coverage 快照至少包含：

- 四种题型小题与语篇数；
- 五档难度分布；
- 册次分布；
- 话题覆盖及选必一+选必二占比；
- 超纲率；
- 库内语篇/题干重复度；
- 语法填空每个 grammar ID 的题量，任一 ID 少于 12 题时在 Coverage 中标记为不足；
- 已发布、审核中、拒收数量；
- 生成时间和数据版本。

后台激活前必须支持任意两个 Bank 的 Coverage 并排对比，以及各抽 5 题预览质量。

## 8. 题型呈现模板（CO-004）

- `cloze`：语篇内多空，每个空在语篇后以 A/B/C/D 四选一作答。
- `grammar_fill`：120–180 词语篇，空位使用 ①–⑩ 编号；语篇后列 10 个四选一小问，取消手输填空。四个选项必须属于同一语法范畴，例如同一动词的不同时态或同一派生词族。题型 ID、`grammar_tags` 与每 ID ≥12 题的 Coverage 要求保持不变。
- `gap_fill`：保留七选五，属于选择题。
- `reading`：保留阅读选择题。
- 每道题必须带 `presentation.mode`、`passage_order`、`question_order`、`blank_label` 和 `option_layout`；组卷按 `(passage_order, question_order)` 输出，禁止前端补排序。

## 9. M1 例外

Demo Bank 为 80 题 / 11 篇，M1 允许同题重复。“7 天内同题重复率 <10%”推迟到 M3，不要求 M1 额外实现该去重约束。Bank 隔离、两条选题规则和计时规则不得豁免。

## 10. 报告留存

- 每次已交卷练习必须持久化完整题目快照、选项、用户作答、正确答案、对错和解析。
- 报告标题格式为 `日期-时间-题目数-分数`。
- 学生可列出、打开并删除自己的历史报告。
- 删除报告时同步删除该会话的题目快照与作答；知识点掌握和错题学习状态不作为报告正文副本删除。
- 未交卷会话允许学生确认退出；退出时在同一事务中删除该会话的题目快照和作答，不生成报告。
