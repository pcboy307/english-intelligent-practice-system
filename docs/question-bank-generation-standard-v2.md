# 大模型题库生成与往返评审标准 v2

状态：冻结版。
适用对象：生成新题库的大模型、评审或修改已导出题库的大模型、题库导入校验器。
机器契约：`contracts/schemas/bank-import-package.json`、`contracts/m26-generation-params-v2.json`。

本文是唯一有效的题库生成标准。旧版提示词、旧字数范围和历史临时说明不再具有约束力。

---

## 一、先选择任务模式

模型接到任务后，必须先判断属于哪一种模式。

### A. 新题库生成模式

按本文的 Schema、题型数量、M2.6 规则生成完整 JSON。

### B. 导出题库评审模式

用户提供系统导出的 `bank-v1` JSON。模型只检查内容、结构、答案和解析，输出评审意见，不擅自重写题库。

### C. 导出题库修改模式

用户要求修改导出题库时：

1. 保留 JSON 顶层文件和 `passage_group_id`；
2. 把所有被修改语篇的 `validation_profile` 从 `stored` 改为 `m26`；
3. 若整包都要重新验收，建议把全部语篇改为 `m26`；
4. 修改后重新计算 `target_size`、`composition`、`word_count`；
5. 更新 `generated_at`；
6. 修改 `name`，追加 `#revised-<序号>`，避免导入时名称重复；
7. 最终输出完整、可重新导入的 JSON。

不能把 `stored` 当作绕过内容校验的标记。`stored` 只表示该包来自数据库导出。

---

## 二、自动校验与质量门禁的分工

### 机器硬校验

以下规则由导入器和脚本自动检查：

- JSON 结构、字段、题型数量；
- `target_size` 与 `composition`；
- 选项数量、答案文本或字母；
- grammar ID、册次格式和册次交集；
- 占位符数量与编号；
- 答案及屈折形式是否在整篇正文再次出现；
- 阅读证据句是否为正文逐字符子串；
- M2.6 词数、长句数、Flesch、阅读题型比例；
- M2.6 完整题库的难度、册次和题材配额。

### Pro/人工门禁

以下规则无法由当前正则校验器完全证明，必须由 Pro 模型或人工复核：

- 答案代回空位后，整句是否语法成立；
- 同一空四个选项是否属于同一词类、同一形态层级；
- 选项是否只有一个唯一最佳答案；
- 语篇是否连贯，而不是互不相关的句子拼接；
- 阅读理解是否真正考查理解，选项是否无歧义；
- 近义词辨析是否真实成立，而不是三个明显错误选项。

**可解性要求：**

每个完形和语法空位都必须把正确答案代回原句。主谓完整、及物性、可数性、介词搭配、时态、语态和非谓语关系必须全部成立。任一空 `INVALID`，整篇拒收。

机器无法证明上述要求时，必须标记为 Pro/人工门禁，不得声称已完成机器自动验证。

---

## 三、单文件顶层契约

最终输出必须是一个 UTF-8 JSON 对象，不得包含 Markdown 围栏、注释、尾逗号或 JSON 外说明。

顶层只允许以下 7 个字段：

```json
{
  "format_version": "bank-v1",
  "name": "M2 Bank #2",
  "target_size": 300,
  "difficulty_profile": "standard",
  "generated_at": "2026-11-09T12:00:00+08:00",
  "composition": {
    "cloze": 6,
    "grammar_fill": 6,
    "reading": 25,
    "gap_fill": 10
  },
  "passages": []
}
```

### `format_version`

- `bank-v1`：普通题库、分批文件、数据库导出、局部修改包；
- `m26-v1`：只用于完整 `72 篇 / 500 题` M2.6 全量题库。

### `name`

- 1–80 个字符；
- 正式完整题库应使用稳定名称；
- 分批中间文件使用 `正式名称#batch-01`；
- 修改后的导出包使用 `原名#revised-01`；
- 数据库导入时名称必须全局唯一。

### `target_size`

必须是文件中所有题目的实际总数，不是计划总数。

### `composition`

必须填写各题型的**实际语篇篇数**，不是题目数。

### `generated_at`

填写 ISO 8601 时间。

### 状态字段

生成文件不得填写 `bank_id`、`bank_tag`、`status`、`created_at`、`updated_at`。这些字段由导入器和数据库管理。

导入成功后由服务端自动设为 `active`。生成模型不得自行写 `ready`、`active` 或 `published`。

---

## 四、生成粒度与合并规则

一次只生成一篇语篇及其全部题目。

执行流程：

1. 先生成单篇 JSON；
2. 对该篇执行结构、数量、占位符、答案、词数、grammar 和阅读证据校验；
3. 不合格则修复或重新生成该篇；
4. 所有单篇通过后，由脚本合并到同一个 `passages[]`；
5. 合并脚本必须统一检查顶层字段；
6. 重新计算 `target_size` 和 `composition`；
7. 只有合并完成后才使用正式完整题库名称。

禁止一次要求模型稳定输出 72 篇。模型输出上限由实际上下文和 token 能力决定，不以固定“4 篇”作为系统常量。

---

## 五、语篇字段

每个 `passages[]` 元素必须包含：

```json
{
  "validation_profile": "m26",
  "type": "reading",
  "passage_group_id": "M26-A-READING-01",
  "topic": "科技",
  "book_source": "选必二 U1",
  "difficulty": 4,
  "word_count": 373,
  "flesch_reading_ease": 48.67,
  "passage": "Original English passage...",
  "questions": []
}
```

规则：

- `type` 只能是 `cloze`、`grammar_fill`、`reading`、`gap_fill`；
- 新生成内容使用 `validation_profile: "m26"`；旧 M2 内容可使用 `"m2"`；
- `validation_profile: "stored"` 只用于系统导出；
- `passage_group_id` 在文件中必须唯一；
- `topic` 使用自然中文题材名；
- 每篇 `difficulty` 和每道题 `difficulty` 都是 1–5 的整数；
- 全库难度配额按**题目级** `difficulty` 统计，篇级难度只表示整体难度；
- `word_count` 与 `flesch_reading_ease` 是说明字段，后端会从正文重新计算，不信任自报值；
- `generation_observations` 若填写，必须是 JSON 对象，不得是数组。

### `book_source` 唯一规范

只允许以下格式：

```text
必修1 U1
必修2 U3
必修3 U5
选必一 U1
选必一 U2
选必二 U1
选必二 U3
跨册综合
```

解析规则：

```regex
^(?:必修[1-3] U[1-5]|选必一 U[1-5]|选必二 U[1-5]|跨册综合)$
```

`必修一 U1`、`选必1 U1`、`跨册` 等都不是新生成文件允许的写法。导入器会报 `BOOK_SOURCE_FORMAT_INVALID`。

---

## 六、四种题型

| 题型 | 每篇题数 | 每题选项 | 历史 M2 词数 | M2.6 硬性词数 |
| --- | ---: | ---: | ---: | ---: |
| `cloze` | 15 | 4 | 170–220 | **280–320** |
| `grammar_fill` | 10 | 4 | 120–180 | **220–260** |
| `reading` | 4 | 4 | 不超过 250 | **350–420** |
| `gap_fill` | 5 | 7 | 不超过 220 | **320–380** |

170–220、120–180 等历史范围只允许 `validation_profile: "m2"` 使用。`m26` 不得使用历史范围；表中 M2.6 数字全部是硬性上下限，不是建议值。

### 6.1 完形填空

- 正文按顺序出现且只出现一次 `(1) ______` 至 `(15) ______`；
- 每个空正好 4 个互不重复的选项；
- 四个选项必须同一词类、同一形态层级；
- 答案代回后必须形成合法英语句子；
- 正确答案及其 exact、不规则屈折和规则后缀形式，在整篇正文内的出现次数必须为 0；
- 派生词不计入泄漏判定；
- M2.6 正文 280–320 词，至少 4 个长度不少于 25 词的长句；
- M2.6 正文平均句长不少于 15 词；
- M2.6 至少出现非谓语、名词性从句、插入语/同位语、倒装/省略四类中的 3 类；
- M2.6 至少 3 道近义辨析题；
- M2.6 Flesch Reading Ease 为 45–60；
- 禁止只考词形变化。

近义辨析题填写：

```json
{
  "near_synonym_calibration": true,
  "context_clue": "判断该空的原文依据",
  "clue_argument": "为何该依据只能推出正确答案"
}
```

`near_synonym_calibration` 是布尔值，不是自由文本。

### 6.2 语法填空

- 正文按顺序出现且只出现一次 `① ______` 至 `⑩ ______`；
- `cloze` 和 `gap_fill` 才使用 `(1)` 等圆括号编号；
- 每题 4 个选项，四个选项属于同一语法范畴；
- 答案代回后必须形成语法正确、语义自然的完整结构；
- 每题填写 `grammar_category`；
- M2.6 十题中必须同时出现：

```text
non_finite_perfect_passive
preposition_plus_which
what_noun_clause
subjunctive
inversion
```

`grammar_category` 的新生成规范值只能是：

- 21 个 grammar ID 之一；
- `relative_clause`、`adverbial_clause`、`noun_clause` 之一；或
- 五个 M2.6 结构类别之一。

旧导入包中的 `时态语态`、`冠词` 可读取，但新生成必须使用 `tense_system`、`articles`。

### 6.3 阅读理解

- 每篇正好 4 道理解题；
- 不得出“哪一句包含某语法结构”的元语言题；
- 每题必须填写 `reading_type` 和 `evidence_sentence`；
- `evidence_sentence` 必须逐字符存在于正文中；
- 正确答案不得与正文连续重合 5 个或以上单词；
- M2.6 正文 350–420 词，平均句长不少于 20 词，Flesch 为 45–60；
- 每篇至少 1 道 `paragraph_function`；
- M2.6 每篇高阶题比例不少于 60%，即 4 题中至少 3 题属于高阶类型。

`reading_type` 允许：

```text
main_idea
detail
inference
vocabulary_in_context
purpose_or_attitude
paragraph_function
```

高阶类型：

```text
main_idea
inference
vocabulary_in_context
purpose_or_attitude
paragraph_function
```

`detail` 不属于高阶类型。

### 6.4 七选五

- 正文按顺序出现且只出现一次 `(1) ______` 至 `(5) ______`；
- 每篇正好 5 题；
- 语篇级 `options` 必须正好有 A–G 七个互不重复的句子；
- 每题 `answer` 是 A–G 单字母；
- 每题填写 `cohesion_type`；
- 单篇至少覆盖 3 种不同衔接类型；
- M2.6 正文 320–380 词，使用说明文或议论文，主题必须具有抽象性。

`cohesion_type` 允许：

```text
pronoun_reference
logical_connector
lexical_repetition
semantic_contrast
time_order
general_to_specific
```

推荐使用篇级选项：

```json
{
  "options": {
    "A": "First option.",
    "B": "Second option.",
    "C": "Third option.",
    "D": "Fourth option.",
    "E": "Fifth option.",
    "F": "Sixth option.",
    "G": "Seventh option."
  }
}
```

题目 `options` 可以省略；若填写必须与篇级七个选项完全一致。

---

## 七、题目字段与答案形态

每题必须包含：

```json
{
  "number": 1,
  "stem": "Question stem.",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "answer": "Option B",
  "explanation": "中文解析。说明答案依据。说明两个主要干扰项为什么错误。",
  "knowledge_points": ["阅读理解：因果关系判断"],
  "grammar_tags": ["noun_clauses"],
  "book_source": "选必二 U1",
  "difficulty": 3
}
```

`question.number` 必须在每篇内从 1 连续递增。

### `answer` 存储形态

按题型固定：

- `cloze`：保存正确选项的完整文字，例如 `"anxious"`；
- `grammar_fill`：保存正确选项的完整文字，例如 `"Although the weather changed"`；
- `reading`：保存正确选项的完整文字；
- `gap_fill`：保存字母，例如 `"A"`。

### 解析

- 必须使用中文；
- 语法术语使用中文，可夹英文原句；
- 至少三句；
- 必须说明正确答案依据；
- 必须明确指出两个主要干扰项为什么错误；
- 不能只写“其余选项不符合语境”。

### 知识点

- 必须是学生能读懂的中文；
- 不得出现 `team_noun`、`material_noun` 等内部 key。

### 禁止字段

不得添加 Schema 之外的字段，尤其不得添加 `cloze_tier`。

允许的题目字段只有：

```text
number
stem
options
answer
explanation
knowledge_points
grammar_tags
book_source
difficulty
evidence_sentence
reading_type
grammar_category
cohesion_type
context_clue
clue_argument
near_synonym_calibration
```

---

## 八、Grammar ID 与册次交集

只允许以下 21 个 grammar ID：

```text
relative_clauses_defining
relative_clauses_non_defining
passive_voice_tenses
past_participle_nonfinite
v_ing_nonfinite
noun_clauses
adverbial_clauses
subjunctive_basic_if
subjunctive_basic_should
partial_inversion_basic
cleft_basic
tense_system
subject_verb_agreement
articles
prepositions
pronouns
conjunctions
word_formation
comparatives_superlatives
with_compound
infinitive_nonfinite
```

每题使用 1–2 个 grammar ID，不得重复。

允许册次：

| grammar ID | 允许册次 |
| --- | --- |
| `relative_clauses_defining` | 必修 |
| `relative_clauses_non_defining` | 必修、选必一、跨册 |
| `passive_voice_tenses` | 必修、选必二 |
| `past_participle_nonfinite` | 必修 |
| `v_ing_nonfinite` | 必修、选必一、跨册 |
| `noun_clauses` | 必修、选必一、选必二、跨册 |
| `adverbial_clauses` | 必修 |
| `subjunctive_basic_if` | 选必一、选必二、跨册 |
| `subjunctive_basic_should` | 选必一、选必二、跨册 |
| `partial_inversion_basic` | 选必二 |
| `cleft_basic` | 必修、选必一、跨册 |
| `tense_system` | 必修、选必一、选必二、跨册 |
| `subject_verb_agreement` | 必修 |
| `articles` | 必修 |
| `prepositions` | 必修 |
| `pronouns` | 必修 |
| `conjunctions` | 必修 |
| `word_formation` | 必修、选必一、选必二、跨册 |
| `comparatives_superlatives` | 必修 |
| `with_compound` | 必修、选必一、跨册 |
| `infinitive_nonfinite` | 必修 |

该题 `book_source` 解析出的册次，必须位于所有 grammar ID 允许册次的交集。交集为空时，不能生成该双标签题。

---

## 九、完整题库配额

### 9.1 `bank-v1` 分批或普通题库

`bank-v1` 不执行完整 300/500 题配额，只检查：

- 顶层结构与实际题目总数；
- 每种题型每篇的固定题数；
- 每篇自身 `validation_profile` 的内容规则。

这允许 1 篇、6 篇或任意分批文件导入预览。

### 9.2 M2 完整 300 题题库

```text
47 篇 / 300 题

完形填空：6 篇 × 15 = 90
语法填空：6 篇 × 10 = 60
阅读理解：25 篇 × 4 = 100
七选五：10 篇 × 5 = 50
```

题目级难度：

```text
1 档 45
2 档 90
3 档 105
4 档 45
5 档 15
```

### 9.3 M2.6 完整 500 题题库

只有完整文件可使用 `format_version: "m26-v1"`，并且所有篇必须使用 `validation_profile: "m26"`。

```json
{
  "format_version": "m26-v1"
}
```

```text
72 篇 / 500 题

完形填空：12 篇 × 15 = 180
语法填空：12 篇 × 10 = 120
阅读理解：40 篇 × 4 = 160
七选五：8 篇 × 5 = 40
```

题目级难度：

```text
1 档 60
2 档 120
3 档 190
4 档 95
5 档 35
```

全部 500 题按题目计一次册次：

```text
选必二 225
选必一 150
必修 100
跨册 25
```

合计必须为 500。旧值 `113/75/50/12` 合计只有 250，已经废弃，不得使用。

M2.6 允许题材：

```text
科技
环境
健康心理
文化艺术
旅行地理
志愿公益
职业创业
家庭代际
体育竞技
社会伦理
人物传记
自然科普
历史遗产
媒体信息
城市交通
```

完整 M2.6 至少覆盖 15 个题材，每个题材最多 6 篇。

---

## 十、导出题库评审模式

系统导出的 `bank-v1` 包具有以下特点：

- `format_version: "bank-v1"`；
- 每篇 `validation_profile: "stored"`；
- 包含完整正文、题目、答案和解析；
- 七选五包含篇级共享选项；
- 导出文件可以重新导入。

### 评审时

评审模型应重点检查：

1. 题目是否可解；
2. 四个选项是否同词类、同形态层级；
3. 答案是否唯一；
4. 解析是否真正解释答案和两个主要干扰项；
5. 是否存在超纲、歧义、重复或泄露；
6. grammar、reading_type、cohesion_type 是否准确；
7. 语篇是否连贯，题目是否真正对应本语篇。

只评审时输出评审报告，不修改原始 JSON。

### 修改时

修改模型必须输出完整 JSON：

1. 修改的篇设置 `validation_profile: "m26"`；
2. 建议整包都设置为 `m26` 后重新验收；
3. 保留合法 `passage_group_id`；
4. 更新 `name`、`generated_at`、`target_size`、`composition`；
5. 对修改篇重新执行本文全部机器和 Pro 门禁；
6. 输出前执行最终自检。

---

## 十一、导入错误速查

| 错误码 | 含义 |
| --- | --- |
| `M26_PROFILE_MISMATCH` | `m26-v1` 中存在非 `m26` 语篇 |
| `M26_TARGET_SIZE_INVALID` | M2.6 全量题数不是 500 |
| `M26_COMPOSITION_INVALID` | M2.6 各题型篇数不正确 |
| `M26_DIFFICULTY_DISTRIBUTION_INVALID` | 题目级难度分布不正确 |
| `M26_BOOK_DISTRIBUTION_INVALID` | 全库题目册次分布不正确 |
| `BOOK_SOURCE_FORMAT_INVALID` | `book_source` 不是规范格式 |
| `GRAMMAR_TAGS_INVALID` | `grammar_tags` 为空或不在 21 项白名单 |
| `GRAMMAR_CATEGORY_INVALID` | `grammar_category` 不在闭集 |
| `COHESION_TYPE_INVALID` | 七选五衔接类型不在闭集 |
| `ANSWER_WORD_APPEARS_IN_PASSAGE` | 答案或屈折形式在正文泄漏 |
| `PLACEHOLDER_*` | 空位数量、编号或下划线格式错误 |

---

## 十二、最终自检

交付前必须逐项确认：

1. 文件是严格 JSON；
2. 顶层正好 7 个字段；
3. `target_size` 等于实际题数；
4. `composition` 等于实际篇数；
5. `m26-v1` 全篇都是 `m26`；
6. 每种题型每篇题数正确；
7. 语法填空使用 `①–⑩`；
8. 完形使用 `(1)–(15)`；
9. 七选五使用 `(1)–(5)`；
10. 每个 `number` 连续；
11. 答案形态符合题型；
12. 完形答案在整篇正文出现次数为 0；
13. reading 的 `evidence_sentence` 逐字符存在；
14. 阅读答案不与正文连续重合 ≥5 词；
15. grammar ID 在 21 项白名单；
16. `book_source` 属于规范格式；
17. book 册次属于全部 grammar ID 的允许册次交集；
18. 知识点是自然中文；
19. 解析指出两个主要干扰项错误原因；
20. 语篇、题目、选项无抄袭、个人信息和内部 key；
21. 可解性已通过 Pro/人工门禁；
22. 没有 Schema 外字段，尤其没有 `cloze_tier`；
23. 没有 Markdown 围栏或 JSON 外文字。

任一失败都必须修复后重新检查。
