# 配置契约

状态：M0 冻结点。配置键只能来自本文列出的文件，业务代码不得自造键名或写死阈值。

## 1. 文件职责

| 文件 | 职责 |
|---|---|
| `contracts/curriculum.json` | 教材、25 单元、词汇/语法边界、题材、难度、题型与质量规则 |
| `docs/curriculum/grammar-book-matrix.md` | 21 个 grammar ID 的允许册次集合与 400 题覆盖可达性 |
| `docs/question-bank-generation-standard-v2.md` | 大模型生成、评审、修改和往返导入题库的唯一标准 |
| `contracts/vocabulary-whitelist.json` | 规范化词元白名单及教材出处 |
| `contracts/design-tokens.json` | App 与后台唯一视觉事实源 |
| `contracts/admin-auth.md` | 本机回环、管理 token、生成审批和审计契约 |
| `config/practice-modes.json` | 时长、篇数构成与两条选题规则 |
| `config/reporting.json` | 掌握度、趋势与报告阈值 |
| `config/validation.json` | 题库自动校验阈值 |
| `config/app.json` | 身份、计时权威、离线与数据清除 |
| `config/api.json` | API 前缀、分页和时延目标 |

## 2. 关键键

### `contracts/curriculum.json`

- `counting_clarification.content_alignment_units`：整数，固定 `25`。
- `counting_clarification.vocabulary_counting`：说明词汇按规范化词头计，并给出 2022 课标基础层、高中新增层、闭合功能词和短语的计数口径。
- `counting_clarification.grammar_counting`：说明语法按项目 ID 计。
- `grammar_tag_policy.max_grammar_tags_per_question=2`：每题一个主 grammar ID，可再带一个跨单元次 ID；Coverage 可重叠计题次。
- `book_tag_policy`：每道考点题必须且只能有一个册次标签，合法值为 `必修/选必一/选必二/跨册`。
- `grammar_whitelist[].allowed_book_tags`：每个 grammar ID 可使用的册次集合；册次标签不随 grammar tag 数量重复计数。
- `vocabulary.counting.base_compulsory_declared_entries`：教育部 2022 三级词表原文声明，固定 `1600`。
- `vocabulary.counting.base_compulsory_single_words`：官方基础层规范化单词头，固定 `1603`；官方原文声明 1600 个印刷条目，差异来自斜杠变体展开。
- `vocabulary.counting.base_compulsory_phrases`：官方基础层遗留短语，固定 `4`。
- `vocabulary.counting.official_supplement_single_words`：课标补充词表单词头，固定 `120`。
- `vocabulary.counting.official_supplement_phrases`：课标补充词表短语，固定 `44`。
- `vocabulary.counting.high_school_unique_entries`：人教版必修 1-3 与选必 1-2 去重条目，固定 `1846`。
- `vocabulary.counting.closed_class_added`：前两层未覆盖的闭合功能词补充，固定 `5`。
- `vocabulary.counting.single_word_entries`：合并去重后的单词头，固定 `3021`。
- `vocabulary.counting.phrase_entries`：多词短语，固定 `392`，不得混入单词头分母。
- `vocabulary.counting.unique_whitelist_entries`：完整允许表，固定 `3413`。
- `vocabulary.normalization.inflections`：入库只保存基础词头；运行时做规则/不规则词形还原。
- **生词率匹配规则**：先按最长匹配识别已登记短语；被短语消费的词元不进入单词分母。剩余单词按词头/lemma 匹配，单词分母为 `denominator_tokens`；`unknown_ratio = unknown_lemma_tokens / denominator_tokens`。短语条目只用于匹配，不作为单词加入分母。
- 生词率阈值 `0.03` 只用于自动筛查，不替代高阶难词排除、非白名单考点为零和语法白名单检查。
- `difficulty.bank_default_distribution.d1...d5`：全库难度占比，分别为 `0.15/0.30/0.35/0.15/0.05`。
- `difficulty.paper_distribution`：单套易中难占比 `0.40/0.40/0.20`。
- `difficulty.paper_hard_adaptive_min/max`：自适应难档下限/上限 `0.15/0.25`。
- `difficulty.max_d5_questions_per_paper`：单套 5 档题上限 `3`。
- `book_distribution.question_point_distribution`：考点册次 `0.20/0.30/0.45/0.05`。
- `book_distribution.reading_topic_min_elective_share`：阅读与七选五选必一+选必二话题下限 `0.50`。
- `question_type_distribution.standard_2000`：生产 Bank 规模。
- `question_type_distribution.demo_80`：M1 Demo Bank 规模，共 80 题 / 11 篇。
- `passage_rules.word_limits`：各题型词数边界。
- `grammar_fill` 仅为题型 ID：语篇使用 ①–⑩ 空位，小题为 A/B/C/D 四选一；干扰项必须同语法范畴，`grammar_tags` 和每 ID ≥12 题覆盖要求不变。
- `cloze` 与 `gap_fill` 使用 `(n)` 编号；`grammar_fill` 使用 `①–⑩`。
- `book_source` 只允许 `必修1-3 U1-5`、`选必一 U1-5`、`选必二 U1-5`、`跨册综合`。
- 新生成文件的 `grammar_category` 使用 grammar ID 或五个 M2.6 结构类别；旧中文值仅保留导入兼容。
- `quality_gates.generation_batch_max_passages`：脚本合并批次上限 `10`；
  大模型单次响应固定只生成 `1` 篇，通过后再由脚本合并。
- `m1_exemption.seven_day_repeat_rate_requirement`：值为 `deferred_to_m3`。

### `config/practice-modes.json`

- `modes.30.passage_composition`：每套固定 1 篇完形、1 篇语法填空、1 篇阅读或七选五。
- `selection_policy.rules`：只有两条选题规则。
  1. 先最小化组合内 3 篇语篇的本学生覆盖次数总和；一篇的覆盖次数按已交卷或已过期会话去重计数。
  2. 覆盖次数总和并列时，优先选择覆盖 3 个不同话题的组合。
- `selection_policy.candidate_order`：固定为 `lowest_total_passage_coverage_count`、`highest_distinct_topic_count`，不得插入其他排序条件。
- 错题标签、历史权重、册次、难度、grammar tag 重复、知识点重复、错题池占比和未完成会话同篇冲突均不参与选题。
- `bank_scope.source`：必须为 `session.bank_id`；`allow_cross_bank_sampling=false`。
- 报告和历史记录必须使用实际题数作分母。

### `config/reporting.json`

- `mastery.ewma_alpha=0.3`。
- `mastery.scope=knowledge_point_cross_bank`。
- `weak_threshold=0.60`、`weak_min_attempts=3`。
- `mastered_threshold=0.85`、`mastered_min_attempts=5`。
- `trend.window=5`、`rising_above=0.05`、`falling_below=-0.05`。
- `stage_report.require_cross_bank_notice=true`。
- `weakness_analysis.active_provider`：当前为 `deepseek`；`qwen` 适配保留用于同题对照，最终采用方由效果与成本决定。
- DeepSeek 薄弱点分析读取 `contracts/generation-model.json`；密钥只从 `DEEPSEEK_API_KEY` 环境变量读取。
- 每次分析结果附带 provider、输入/输出 token、耗时与估算人民币成本，报告正文仍只持久化 300 字以内文案和 `llm/fallback` 来源。
- 薄弱点分析输入必须包含题目、用户答案、正确答案和知识点；输出超过 300 字时按完整句截断。

### `config/validation.json`

- 超纲生词率上限 `0.03`。
- 每篇非白名单词最多 `2` 个，必须有中文释义且不得作考点。
- `grammar.book_tag_must_be_in_grammar_tag_intersection=true`：题目所有
  grammar tag 的允许册次交集必须包含唯一 `book_tag`；空交集拒收并返回
  `BOOK_TAG_INCOMPATIBLE`。
- Bank 内语篇相似度 `>=0.90` 拒收，题干 `>=0.85` 拒收。
- 解析至少 `3` 句。
- 首批 `10` 篇后必须暂停。

### `config/app.json`

- `time_authority=server_deadline`。
- `answer_available_before_submit=false`。
- `data_clear_scope` 同时包含本地缓存和后端该 ID 数据。
- `student_identity.web_storage=localStorage`；Web 本地演示可用，但安全等级低于原生安全存储。
- `student_identity.native_storage=expo-secure-store`；回到手机端时必须恢复原生安全存储。
- `web_layout.mobile_max_width=480`；`desktop_breakpoint=768`；`desktop_max_width=960`；正文块 `body_max_width=760`。
- `web_layout.color_scheme=light`；CSS 必须固定 `color-scheme: light`。
- `design-tokens.json.web_desktop` 固定选项字号 15、行高 1.5、内边距 12、高度 40、间距 8、按钮高度 40。
- `control.touchTargetMin=44` 仅适用于移动端；桌面端使用 `web_desktop` 的收紧尺寸。
- 练习页一次显示一题；所有操作按钮位于内容区右上角。
- 交卷和退出均使用页面内确认弹窗；退出未交卷练习时必须删除会话、题目快照和作答，且不得生成报告。

### `config/api.json`

- 后端固定 `0.0.0.0:8000`。
- Expo Web 固定 `localhost:8081`。
- `cors.allow_origins` 只能是 `http://localhost:8081` 与 `http://127.0.0.1:8081`。
- 禁止 `*`、禁止 `wildcard_allowed=true`。

### `contracts/admin-auth.md`

- 服务绑定 `0.0.0.0`。
- `/admin/*` 默认先校验回环来源，再校验 `X-Admin-Token`。
- `POST /admin/banks/{bank_id}/activate` 与 `/maintenance/*` 是例外：只校验回环来源，不校验口令。
- `ADMIN_TOKEN` 仅来自 `.env`；缺失时启动生成并写回。
- 禁止用 `X-Forwarded-For` 判断来源。
- token 使用 `secrets.compare_digest`。
- 管理写操作写 `admin_audit_log`，仅保存 token SHA-256 前 8 位。

## 3. 修改规则

只有 Lead Agent 可修改 `contracts/` 与 `config/`。任何子 Agent 需要新键、阈值或设计值时必须上报，由 Lead 评估并同步 Schema、OpenAPI、测试与 `CHANGELOG.md`。未登记键视为契约错误。
