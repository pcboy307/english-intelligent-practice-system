# 高二英语智能练习系统设计

日期：2026-11-07  
状态：M0 冻结候选  
需求依据：仓库根目录 V11 需求文本、`contracts/curriculum.json`、`contracts/bank-model.md`、`contracts/design-tokens.json`

## 1. 目标与边界

系统面向广东省高二学生，在人教版（2019）必修 1–3 与选择性必修 1–2 范围内提供四题型练习、自适应组卷、错题复现和结构化报告。第一期只做本地单机开发与真机演示，不做登录、云部署、教师端、家长端、排行榜、付费或暗色模式。

## 2. 总体架构

```text
Expo App
  |  X-Student-Id, JSON API
  v
FastAPI monolith
  |-- api/              HTTP 合同与依赖注入
  |-- services/practice 组卷、判分、错题
  |-- services/reporting EWMA、趋势、报告
  |-- services/question_pipeline Bank/job/校验
  |-- repositories/      SQLAlchemy 持久化
  v
PostgreSQL 16  +  Redis 7
```

后端按 domain/service/repository/api 分层。所有业务规则从 `contracts/` 与 `config/` 读取；禁止在业务模块复制阈值。App 只通过 OpenAPI 合同调用后端，不直接读取数据库。

## 3. 数据与状态

### 3.1 Bank

- Bank 是题目与语篇的隔离边界。
- `draft → generating → reviewing → ready → active/archived`。
- 一个 Bank 只绑定一个 generation job；单批最多 10 篇。
- 首批完成后进入 `paused_for_review`，人工确认后继续。
- active 唯一性由部分唯一索引与状态切换事务共同保证。
- Bank 切换不改写已有 session、report、error tag。

### 3.2 Session

- 创建时快照 Bank ID、名称和版本。
- deadline 在服务端创建，客户端仅展示；到期由服务端自动交卷。
- session item 通过复合外键同时约束 session Bank 与 question Bank。
- 未交卷响应不包含答案或解析。

### 3.3 错题与掌握度

- `error_tags` 以学生、题目、Bank 为业务唯一键。
- `I_err` 仅对当前 session Bank 生效。
- `S_kp` 与 EWMA 掌握度跨 Bank。
- `error_tag_successes` 保存不同会话的答对记录；两次后归档。
- 同套重复不增加 streak。

## 4. 组卷

组卷在纯函数中完成候选过滤、约束评估和带权无放回抽样：

```text
W = 1.0
  + 2.0 * I_err
  + 1.0 * min(S_kp, 3)
  + 0.5 * S_type
  + 0.8 * G_gap
  - 1.2 * R_recent3
  - 0.6 * R_7d
```

`W` 下限为 0.1。候选只读取 `session.bank_id`。单套卷检查易中难、五档上限、册次分布、阅读话题、错题池上限、知识点重复和同篇限制。M1 允许同题重复，但不得绕过完整权重。

## 5. 报告

- 单次报告在交卷事务提交后生成，包含四题型结果、知识点三档、薄弱 Top3 和建议。
- EWMA 更新公式为 `new = 0.3 * score + 0.7 * old`。
- 阶段报告每 5 次自动生成或手动生成，包含最近 5 次趋势斜率和标准差。
- 跨 Bank 区间必须返回 `cross_bank_notice`。

## 6. 题库管线

1. 创建 Bank。
2. 所有者批准后创建生成 job。
3. LLM adapter 按“语篇+小题组”生成。
4. Schema、答案、词数、词汇、语法、题材、难度、相似度、解析长度校验。
5. 拒收项写入 `rejected_questions`。
6. 首批完成后暂停，提交样板与校验报告。
7. 人工审核并通过后发布。
8. 全量完成后计算 Coverage 快照。

LLM adapter 与报告文案 adapter 都通过接口注入，测试使用确定性 fake，不消耗外部额度。

## 7. App

### 7.1 导航

```text
Home
  -> Practice
       -> Report
            -> Analysis
```

M4 增加 Error Book、Trend、Settings。

### 7.2 状态边界

- `device_student_id`：安全存储。
- Session：内存状态 + 本地 session 草稿。
- Answer draft：仅保存学生答案，不保存标准答案或解析。
- Server deadline：每次启动、回前台和提交前重新拉取。
- Report：交卷后从服务端获取并缓存。

### 7.3 视觉

所有颜色、字号、行高、间距、圆角、线宽和触控尺寸从 `contracts/design-tokens.json` 读取并映射为应用内 token 对象。语篇正文使用平台衬线字体，题干和 UI 使用系统无衬线字体。

## 8. 安全与错误处理

- 学生接口强制 `X-Student-Id` UUID。
- 学生只能访问自己的 session/report/error tags。
- 标准答案只存在于服务端题目表；序列化层使用无答案 DTO。
- 过期会话服务端自动交卷，重复提交幂等返回已有报告。
- API 使用 `contracts/error-codes.md` 的统一错误响应。
- 数据清除先删除后端学生数据，成功后清本地缓存；失败时保留本地并提示重试。

## 9. 测试策略

- 契约：JSON Schema、OpenAPI lint、配置键与百分比总和。
- 题库：四题型词数、词汇、语法、题材、答案结构、解析长度、相似度。
- 组卷：权重公式、M1 数量、README 中 2.1/2.3 分布、Bank 隔离。
- 错题：两次不同会话消标、同套不计、换库冻结与跨库知识点。
- 报告：EWMA、薄弱点、趋势、跨库说明。
- API：未交卷答案泄漏、身份隔离、deadline、幂等。
- App：草稿恢复、回前台校准、四页面渲染、tokens 使用、无硬编码颜色。
- QA：grep 色值、可访问触控尺寸、截图人工比对。

## 10. 里程碑

- M0：契约、配置、迁移、逐单元语法清单、任务拆分。
- M1：Demo Bank、完整组卷/错题、单次报告、四页面、容器与测试。
- M2：阶段报告、报告 adapter、后台 Web。
- M3：全量 Bank#1，单批生成与首批暂停。
- M4：App 完善、视觉巡检与完整验收。
- M5：Bank#2 多库验证。
