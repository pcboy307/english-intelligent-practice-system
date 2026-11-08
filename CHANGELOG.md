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
- 所有者签收 CO-003 半天闭环，tag 为 `co003-halfday-closedloop`；M1 明确保持未完成。
- 原始记录：`docs/change-log/CO-003-half-day-sprint.md`、`docs/milestones/M1-half-day-delivery.md`。

## 2026-11-07 - CO-004 练习体验与解析修订

- 版本升为 V11.3。
- 语法填空改为语篇内 ①–⑩ 加语篇后 10 个四选一小问，取消手输。
- 组卷按篇和题号排序，前端按篇分节，进度改为“第 x 篇 / 共 y 篇”。
- 桌面内容区扩展为 960，正文块限制 760，并新增 `web_desktop` 视觉 token。
- 报告解析全部中文化，报告与答题回顾支持双向跳转。
- 新增已交卷会话 review 接口，前端类型由 OpenAPI 生成。
- 原始记录：`docs/change-log/CO-004-practice-experience.md`。

## 2026-11-07 - CO-005 逐题导航与历史报告

- 版本升为 V11.4。
- 练习页改为每次一题，上一题、下一题、查看报告和交卷按钮集中在右上角。
- 薄弱知识点由本地 Qwen 模型根据题目和作答结果生成不超过 100 字的中文建议。
- 报告与题目、选项、作答、正确答案、对错和解析一起持久化，标题格式为日期-时间-题目数-分数。
- 新增历史报告列表、打开和事务化删除；删除报告时同步删除关联题目快照和作答。
- 原始记录：`docs/change-log/CO-005-practice-history.md`。

## 2026-11-07 - CO-006 交卷弹窗与退出练习

- 版本升为 V11.5。
- 交卷确认从页面底部移入居中弹窗。
- 练习页右上角新增退出按钮；二次确认后删除未交卷题目与作答并返回首页，不生成报告。
- 原始记录：`docs/change-log/CO-006-exit-and-dialog.md`。

## 2026-11-07 - CO-007 正确答案绿色高亮

- 交卷后的报告页将每道题的正确答案显示为绿色底、白字标签。
- 已交卷会话的“查看原题”页同步高亮正确选项；错误选择仍保留黑色选中态并由结果文字标明。
- 语义绿填充仅限正确答案，不允许扩大到错误答案或大面积界面。
- 原始记录：`qa/evidence/correct-answer-review.png`。

## 2026-11-07 - M2.0 生成管线试点

- 新建 `M2 Bank #2`，目标 300 题；试点失败后保持 `generating`，题量为 0，禁止继续追加或放量。
- 使用本机 `qwen3.5:4b-q4_K_M` 真实生成完型试点，最大重试 3 次，总 token 预算 120000。
- 4 次尝试全部未通过闸门，试点失败率 100%；可观测 token 为 4124，3 次运行未返回可用 JSON/usage。
- 失败分类：structure 32、grammar_tag 2、book_tag 1、question_count 1、vocabulary_scope 1。
- 证据：`qa/evidence/m2/generation-cost-report.json`、`qa/evidence/m2/gate-failures.json`、`qa/evidence/m2/bank2-counts.txt`。

## 2026-11-07 - M2.0b DeepSeek 试点停止线

- 按所有者指令改用云端 `deepseek-flash`（DeepSeek-V4.1-Flash-1017）；本地 Qwen 仅保留为薄弱点分析对照。
- 新增 JSON mode、`finish_reason` 强制记录、三步拆分、3 次修复重试、3 次传输重试、5 次连续失败熔断和 80% 预算停止线。
- 真实 `/models` 验证和 1-token ping 通过，模型 ID 回填为 `deepseek-flash`。
- 第一批 5 题请求中 4/5 因 `finish_reason=length` 失败，请求级失败率 80%，超过 30% 停止线，停止重跑。
- 根因为 DeepSeek 默认 thinking 模式占用 4096 输出预算；已关闭 JSON 生成请求的 thinking，但尚未获准重跑。
- 本轮观测成本人民币 0.168266 元；Bank #2 仍为 0 题，两个 generation job 均为 failed。
- 证据：`qa/evidence/m2b/`。

## 2026-11-07 - M2.0b 关闭 thinking 后重跑

- PostgreSQL 前置校验通过：端口 15432、库名 `english_practice`、会话 411，高于历史基线 42。
- `max_tokens` 由 4096 提高到 8192，并显式设置 DeepSeek `thinking.type=disabled`。
- 单请求 5 题烟测通过：`finish_reason=stop`，输入 633 tokens、输出 373 tokens、成本 0.00425 元。
- 完整试点在完型解析批次失败：4/8 个生成请求返回非对象 explanation，请求级失败率 50%，再次触发 30% 停止线。
- 本轮 8 个请求 `finish_reason` 全部为 `stop`，不存在截断；失败类别为 `validation_error / EXPLANATION_NOT_OBJECT`。
- 本轮观测成本 0.062964 元；未写入 Bank #2，未执行浏览器验收或 v4-pro 对照。

## 2026-11-07 - M2.0b explanation 契约对齐

- 零成本诊断确认 V11 与 `question.json` 均要求 `explanation` 为字符串；原校验器要求对象，属于校验器违背契约。
- 已修正中间解析批校验为字符串数组，并为结构错误附带实际类型和样例。
- 新增每次 DeepSeek 响应的原始文本落盘，单文件截断到 8000 字符。
- 结构修复重试上限由 3 次降为 1 次；429/超时/5xx 仍按 3 次指数退避。
- 10 条解析冒烟未通过：模型仍返回对象数组，`finish_reason=stop`，已保留完整原文并按规则停止，未再次请求。
- 上一轮 8 个请求中，同一结构错误产生 3 次重试，浪费 6002 tokens，估算 0.027244 元。

## 2026-11-07 - M2.0b 批量解析 IR 契约

- 新增 `contracts/schemas/generation-batch.json`，固定 explanation 批响应为带 `question_index` 的对象数组。
- IR 层使用 JSON Schema 校验；索引必须无重复、无缺号、无越界，并按索引排序映射。
- 最终 100 字以内解析继续使用 `question.json` 的字符串定义做第二次校验。
- 原始模型响应统一落盘到 `qa/evidence/m2b/raw-responses/`，最多保存 8000 字符。
- 结构修复重试降为 1 次；429/超时/5xx 仍最多指数退避 3 次。
- DeepSeek structured output `json_schema` 冒烟返回 HTTP 400：`This response_format type is unavailable now`，按冒烟规则停止，没有自动回退。
- 经用户批准后退回显式 `json_object`，提示词版本升级为 `m2-gen-v2`，IR Schema 原文和两条对象样例直接嵌入提示词。
- `json_object` 冒烟：10 条解析完整生成、`finish_reason=stop`、输入 1286 tokens、输出 932 tokens、成本 0.010028 元。
- IR Schema 因第 10 项包含额外空字段 `explanation_extra` 拒收整批；原文已落盘，未重试、未进入完整试点。
- `deepseek-v4-pro` 的 json_schema 探针同样返回 HTTP 400：`This response_format type is unavailable now`，当前不支持强约束路径。

## 2026-11-07 - Demo Bank 规模笔误修正

- 笔误修正：Demo Bank 由文档中的“60 题/11 篇”统一改为“80 题/11 篇”。
- 分题型构成不变：完型 30 + 语法 20 + 阅读 20 + 七选五 10 = 80。
- 本次不是需求放宽，也不改变 V11.5 版本号。

## 2026-11-07 - M1 Demo Bank 扩库与两层组卷

- Demo Bank 扩展到 80 题、11 篇；本轮新增 8 篇、50 题，未额外生成。
- 新增内容采用确定性人工编写，本轮生成 token 为 0。
- 每篇词数、题数、21 个 grammar ID、生词率和高阶词抽检全部通过。
- 册次配额改用最大余数法；29 题 `13/9/6/1`、30 题 `14/9/6/1`、
  42 题 `19/13/8/2` 均有单测。
- 组卷改为硬约束骨架筛选后再按 W 软排序；四套连开日志与四条判定证据见
  `qa/evidence/m1/`。
- 四套连开的 grammar tag 最大值均为 3，册次配额全部通过，近期题权重
  `0.4 < base_weight=1.0`，并发未完成会话语篇交集为空。
- 扩库后本地模型薄弱点分析返回中文 77 字，满足不超过 100 字要求。
- 全库精确五档分布仍登记为后续待补齐项；本次不改变 V11.5 版本号。

## 2026-11-07 - M1 签字前补充

- 明确 8 篇 50 题是确定性人工编写，未经过 AI 生成管线；生成管线端到端验证属于 M3。
- 薄弱点模型记录为 `qwen3.5:4b-q4_K_M`，本机 `llama.cpp` 部署；强制断网时实测
  返回规则版 fallback。
- LLM 分析增加显式“建议：”动作校验，修复“现在完成时”中的“先”被误判为建议词。
- “同语篇不拆两卷”定稿为 B：同一语篇不得同时进入两套未完成会话，已交卷会话可复用。
- 单套难度 40/40/20 作为硬约束实测通过：29 题 `12/11/6`，30 题 `12/12/6`。
- 全库五档分布判定为 M1 豁免、M3 补齐；80 题 Demo 不冒充精确达标。

## 2026-11-07 - M0 语法集合与册次重算

- 7 个聚合 grammar ID 建立授权子项集合 S，25 单元按集合关系重判。
- 新计数：完全一致 2、教材范围更窄 18、教材范围更宽 2、白名单外 3。
- V11 第 4 行原文不含“作宾语”；选必一 U4 只开放作状语，作宾语、作表语禁考。
- 21 个 ID 明确允许册次集合；每道题新增唯一 `book_tag`，grammar tag 不重复计册次。
- `passive_voice_tenses` 允许册次修正为 `{必修, 选必二}`；25 行机械自检 0 处不匹配。
- 210 个 ID 对中 34 对交集为空、176 对兼容；兼容对见证以 132 题覆盖 252 题次，
  可达性结论为“可达”。
- 薄弱点分析答题数表述改为“29 题中答对 23 题”；登记 4B 模型质量观察项。
- 新增 `BOOK_TAG_INCOMPATIBLE` 校验：book_tag 必须属于全部 grammar tag 的允许册次交集。
- 三个非法双标签样例均拒收（两个空交集、一个交集非空但册次不在交集），一个合法
  双标签样例通过。
- 详细记录：`docs/change-log/M0-grammar-book-recalculation.md`。

## 2026-11-07 - 报告与答题回顾锚点

- 从报告第 N 题点击“查看原题”进入回顾后，答题页“查看报告”会携带
  `anchor=N` 返回。
- 报告页在内容完成布局后，只选择当前可见的第 N 题解析块并滚入视口中部。
- 浏览器实测第 10 题目标块 `top=433.31, bottom=645.91`，视口高度 `1080`，
  未停留在页面顶部。

## 2026-11-07 - 薄弱知识点自然语言化

- 薄弱点分析在送入本地模型前，将内部知识 key 转换为学生可读的中文标签。
- 定义 `team_noun`、`material_noun`、阅读技能和七选五衔接等 40+ 个显式标签。
- 新增通用兜底，未知下划线 ID 不再原样展示。
- 真实模型报告不再出现 `team_noun`、`material_noun`，改用
  “名词词义辨析（团队）”“名词词义辨析（材料）”等表达。

## 2026-11-07 - 薄弱知识点分析扩至 300 字

- `config/reporting.json.weakness_analysis.max_chars` 由 100 调整为 300。
- DeepSeek 与 Qwen provider 的 `max_tokens` 均由 220 调整为 500。
- 提示词改为建议 120–260 个汉字、最多不超过 300 个汉字。
- 回归测试覆盖“超过 100 字但不超过 300 字”的模型回复，旧逻辑截断问题已消除。

## 2026-11-07 - 答题页左上角显示当前题型

- 答题页左上角由题库名改为当前题型的自然语言名称。
- 映射：完形填空、语法填空、阅读理解、七选五。
- 浏览器实测逐题切换后标题同步从“完形填空”变为“语法填空”“阅读理解”。

## 2026-11-08 - M2.5 错题本、覆盖统计与软删修正

- 新增 `question_attempts`、`mistake_items`、`report_deletions` 和
  `bank_switch_log`，并为 `practice_sessions` 增加 `session_kind`。
- 交卷时持久化逐题 attempt；错题连续重做答对 2 次进入 mastered，答错立即归零。
- 完形、语法、阅读按题记录错题；七选五使用 `seven:{passage_id}` 按篇记录。
- 新增当前/历史题库分组错题本、完整语篇重做及锁定空位灰字正确答案。
- 历史页新增当前 active bank 的三段覆盖堆积条，以及两个受本机口令保护的清空操作。
- CO-005 的报告删除由物理删除修正为 `report_deletions` 软删。
- 全量验收：118 passed、M0 PASS、API contract PASS calls=18、OpenAPI valid。

## 2026-11-08 - M2.5 鉴权范围修正与首页换库

- 四个 maintenance 接口取消口令校验，保留 127.0.0.1 / ::1 回环限制。
- `POST /admin/banks/{bank_id}/activate` 同样取消口令校验，保留回环限制并继续写
  `bank_switch_log`；其余管理接口口令校验不变。
- 首页题库名称/题数统一取 `GET /stats/coverage`，并新增题库切换入口与两阶段确认。
- 重做页、覆盖条和两个 maintenance 弹窗均重新浏览器验收。
- 新增 questions 复合主键补授权记录、外键完整性审计和查询/写入路径审计。
- 最终回归：122 passed、M0 PASS、API contract PASS calls=20、OpenAPI valid。
