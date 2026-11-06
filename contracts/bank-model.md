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
                                      \-> archived
active -> archived
```

- `draft`：Bank 已创建，尚无运行中的 job。
- `generating`：有且只有一个运行中的 generation job。
- `reviewing`：自动校验完成，等待人工审核。
- `ready`：审核完成且可作为待激活候选。
- `active`：当前生效 Bank，新会话使用。
- `archived`：不再作为激活候选，但所有历史数据保留。
- 任一时刻最多一个 `active` Bank，由 PostgreSQL 部分唯一索引保证。
- 禁止物理删除 Bank；默认不提供物理删除接口。

## 3. 创建与生成

- 创建 Bank 时记录 `name`、`target_size`、`difficulty_profile`、`status=draft`。
- 生成前必须由系统所有者单独批准；API 请求体必须带 `approved_by_owner=true`，服务端仍应配置外部确认门禁。
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
- 同语篇不得拆到两套练习。
- Bank 切换只改变之后创建的新会话。

## 6. 错误标签与跨 Bank 语义

主动错题标签以 `device_student_id + question_id + bank_id` 为唯一业务身份，并快照 `knowledge_points` 与 `grammar_tags`。

- `I_err`：只有标签所属 `bank_id` 等于 session Bank 时才产生加权。
- `S_kp`：按知识点/语法标签跨 Bank 统计活跃错题，最多计 3。
- `G_gap`：知识点掌握度跨 Bank 累计，基于 `knowledge_mastery`。
- `streak`：按错误标签所属 Bank 独立冻结和续算；换库不增加、不重置。
- 两次不同会话都答对后转 `mastered`；同套内重复只取该题第一次结果。
- `mastered` 后再次答错，转回 `active` 且 `streak=0`。

## 7. Coverage 与选库

Coverage 快照至少包含：

- 四种题型小题与语篇数；
- 五档难度分布；
- 册次分布；
- 话题覆盖及选必一+选必二占比；
- 超纲率；
- 库内语篇/题干重复度；
- 已发布、审核中、拒收数量；
- 生成时间和数据版本。

后台激活前必须支持任意两个 Bank 的 Coverage 并排对比，以及各抽 5 题预览质量。

## 8. M1 例外

Demo Bank 仅 60 题，M1 允许同题重复。“7 天内同题重复率 <10%”推迟到 M3，不要求 M1 额外实现该去重约束。其余 Bank 隔离、组卷权重、错题和计时规则不得豁免。
