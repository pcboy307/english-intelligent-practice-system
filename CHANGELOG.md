# Changelog

## 2026-11-07 - M0 启动

- 锁定 Node.js 24 LTS、Expo SDK 58、Python 3.12。
- 初始化 Git 仓库，建立里程碑单提交规则。
- 开始冻结 V11 契约、配置、数据库模型与逐单元语法清单。

## 2026-11-07 - M0 决策补充

- 主按钮固定黑底白字；强调色禁止用于按钮、正文、卡片、大面积表面和默认边框。
- 服务绑定 `0.0.0.0`；`/admin/*` 使用 socket 回环来源 + `X-Admin-Token` 双层门禁。
- 生成审批改为服务端持久化记录，不再接受客户端布尔批准。
- 题目审核加入 `bank_id` 与题目归属一致性要求。
- 交卷加入幂等键，重复提交返回同一结果。
- 提交纪律改为每任务一次 commit、每里程碑一个 tag。
- 词汇第一层切换为教育部 2022 课标三级词汇表；ECDICT `zk` 仅作为 29.47% 差异率的审计参照。
- 补齐 25 单元教材语法出处。
- 增加词汇抽检和两篇 M1 语篇生词率证据。

## 2026-11-07 - V11.1 / CO-001

- 用户批准新增基础不定式 `infinitive_nonfinite`，白名单由 14 行、20 项增至 15 行、21 项。
- 仅允许 `to do` 与 `to be done`；禁止完成式、进行式、分裂不定式、`to do`/`doing` 意义辨析和独立不定式设题。
- 必修三 U4 由“白名单外”改为“完全一致”。
- 语法填空 Coverage 要求每个 grammar ID 至少 12 题。
- 原始变更记录：`docs/change-log/CO-001-infinitive.md`。

## 2026-11-07 - PROC-001 执行方式偏差

- 多 Agent 并行复核不可用，实际改为串行执行。
- 主要失败类型为任务单未进入有效子上下文；另有一次 `reasoning_text` 的 `invalid_request_error`，无并发限流证据。
- 工具最多允许主 Agent + 3 个子 Agent，但没有文件锁或写冲突预防，因此同一目录只能单写者串行。
- 本项不影响 M1 验收范围，只影响工期；已登记到待补齐清单。
- 原始记录：`docs/change-log/PROC-001-serial-execution.md`。

## 2026-11-07 - CO-002 学生端改为 Expo Web

- 版本由 V11.1 升为 V11.2；当前版本统一读取 `contracts/VERSION`。
- 保留 React Native + Expo，一期以 `react-native-web` 在浏览器运行；真机验收推迟。
- 前端端口固定 8081，后端固定 8000；CORS 只允许两个本机前端源。
- Web 强制浅色、最大宽度 480；身份存储降级为 localStorage，原生 secure store 待回补。
- 原始记录：`docs/change-log/CO-002-web-runtime.md`。

## 2026-11-07 - CO-003 半日冲刺

- 范围收敛为三页、30 题、单次报告和 PostgreSQL 持久化最小闭环。
- 当日排除 60 分钟卷、错题本页、趋势页、后台管理页、手机真机与全量题库。
- PostgreSQL 16.15 使用官方 Windows ZIP 在 15432 端口启动；浏览器闭环已跑通。
- 前端实际调用 6 个端点与 OpenAPI 机械对照全部通过。
- M0 25 单元表改为完全一致 9、教材范围更窄 11、教材范围更宽 2、白名单外 3；补齐 13 个跨单元 grammar ID 归属规则和三个教材抽查点出处。
- 数据库守卫改为 `contracts/runtime.json` 绝对规则：只允许端口 15432 和数据库 `english_practice`；只改 URL 到 5432 时启动被拒绝。
- 后端重启前后 `practice_sessions` 均为 42；报告含分数、3 组题型正确率、3 个薄弱知识点、30 条逐题解析且缺失解析数为 0。
- 登记当前 Demo Bank 只有 30 题/3 篇，以及加权、重复惩罚和知识点上限尚未形成真实排除验证。
- 原始记录：`docs/change-log/CO-003-half-day-sprint.md`、`docs/milestones/M1-half-day-delivery.md`。
