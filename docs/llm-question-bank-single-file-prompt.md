# 大模型单文件题库生成提示词

将下面整段内容作为其他大模型的任务说明。使用前附上：

- `contracts/curriculum.json`
- `contracts/vocabulary-whitelist.json`
- `contracts/quality-bar-v1.md`
- `contracts/high-frequency-cloze-words.json`
- `config/m2-quota-allocation.json`
- `config/m2-full-schedule.json`

缺少任何权威文件时，模型必须停止并要求补充，不得自行编造排程、词表或语法白名单。

---

你是一名高中英语题库数据生成器。你的最终交付物必须是一个 UTF-8 编码、可以被 JSON 解析器直接读取的单个文件：

```text
m2-bank.json
```

你不是在写普通文章或展示 JSON 示例。你必须生成完整的题库数据文件，满足字段、题量、标签、册次和内容质量约束。

## 一、不可违反的总规则

1. 只输出一个顶层 JSON 对象。
2. 顶层只允许以下三个字段：

```json
{
  "schema_version": "1.0.0",
  "bank": {},
  "passages": []
}
```

3. `passages` 必须最终正好包含 47 个完整语篇对象。
4. 47 篇合计必须正好 300 道题。
5. 不得输出 Markdown 代码围栏、注释、尾逗号、省略号、说明文字或“其余略”。
6. 不得用 `...` 省略题目。
7. 不得改变用户提供排程中的：

```text
passage_group_id
type
topic
book_source
difficulty
grammar_tags
题量
```

8. 所有语篇、题干、选项和解析必须原创。不得复制教材、真题、考试机构材料或网络原文。
9. 不得出现真实学校、学生姓名、身份证号、准考证号、班级排名等个人信息。
10. 如果无法在单次输出中稳定完成整个文件，必须先使用代码或文件写入工具分批构造并合并；不得输出残缺文件冒充完成品。

## 二、单文件顶层结构

最终文件必须呈以下结构：

```json
{
  "schema_version": "1.0.0",
  "bank": {
    "bank_name": "M2 Bank #2",
    "target_size": 300,
    "difficulty_profile": "standard",
    "passage_count": 47,
    "question_count": 300,
    "type_counts": {
      "cloze": {
        "passages": 6,
        "questions": 90
      },
      "grammar_fill": {
        "passages": 6,
        "questions": 60
      },
      "reading": {
        "passages": 25,
        "questions": 100
      },
      "gap_fill": {
        "passages": 10,
        "questions": 50
      }
    }
  },
  "passages": []
}
```

`bank_id`、数据库状态创建时间和更新时间由导入器生成。生成模型不得擅自把 Bank 标成 `ready`、`active` 或 `published`。

## 三、单个 passage 对象

`passages[]` 中每个元素必须使用以下结构：

```json
{
  "validation_profile": "m2",
  "passage_group_id": "M2-FULL-READING-01",
  "type": "reading",
  "topic": "环境保护",
  "book_source": "选必一 U1",
  "difficulty": 3,
  "passage": "Original English passage.",
  "questions": []
}
```

必填字段：

```text
validation_profile
passage_group_id
type
topic
book_source
difficulty
passage
questions
```

`type` 只能使用：

```text
cloze
grammar_fill
reading
gap_fill
```

`book_source` 必须能够解析为且只解析为一个册次：

```text
必修
选必一
选必二
跨册
```

## 四、四种题型的结构

| type | 每篇题数 | 词数 | 每题选项数 |
|---|---:|---:|---:|
| `cloze` | 15 | 170–220 | 4 |
| `grammar_fill` | 10 | 120–180 | 4 |
| `reading` | 4 | 1–250 | 4 |
| `gap_fill` | 5 | 1–220 | 7 |

### 4.1 完形填空

语篇中必须按顺序出现：

```text
(1) ______
(2) ______
...
(15) ______
```

每个编号只能出现一次。`questions` 正好 15 道。

每题：

- 4 个不同选项；
- 正确答案必须与某个 option 完全相等；
- 正确答案及其词形变化不得出现在题干或空格附近；
- 不得只考词形变化，必须依靠上下文辨析；
- 单篇必须是连贯语篇，不得拼接互不相关的句子。

允许并建议加入：

```json
{
  "context_clue": "判断该空所依据的原文线索",
  "clue_argument": "该线索为什么能推出答案",
  "cloze_tier": "easy"
}
```

`cloze_tier` 只能是：

```text
easy
medium
hard
```

### 4.2 语法填空

语篇中必须按顺序出现：

```text
① ______
② ______
...
⑩ ______
```

每个标记只能出现一次。`questions` 正好 10 道。

每题：

- 4 个选项；
- 四个选项属于同一语法范畴；
- 正确答案与某个 option 完全相等；
- 解析必须使用中文语法术语，可夹英文原句；
- 单篇至少覆盖 5 个语法类别。

### 4.3 阅读理解

语篇不超过 250 词。`questions` 正好 4 道。

每题必须包含：

```json
{
  "stem": "Comprehension question",
  "options": ["option 1", "option 2", "option 3", "option 4"],
  "answer": "option 2",
  "explanation": "中文解析第一句。中文解析第二句。两个主要干扰项为什么错误。",
  "knowledge_points": ["阅读理解：细节定位"],
  "grammar_tags": ["articles"],
  "book_source": "选必一 U1",
  "difficulty": 2,
  "reading_type": "detail",
  "evidence_sentence": "must be an exact substring of passage"
}
```

`reading_type` 只能使用：

```text
main_idea
detail
inference
vocabulary_in_context
purpose_or_attitude
```

`evidence_sentence` 必须是 `passage` 中逐字符存在的完整子串，不能改写、翻译或拼接。

阅读题必须是理解题，禁止出现“哪一句包含某语法结构”一类元语言题。正确答案不得连续复制原文 5 个以上单词。

### 4.4 七选五

语篇不超过 220 词，并按顺序出现：

```text
(1) ______
(2) ______
(3) ______
(4) ______
(5) ______
```

`questions` 正好 5 道。每题携带完整 7 个选项，选项文本使用：

```text
A. ...
B. ...
C. ...
D. ...
E. ...
F. ...
G. ...
```

每题必须包含：

```json
{
  "answer": "A",
  "cohesion_type": "logical_connector"
}
```

七选五的 `answer` 必须是 A–G 中唯一一个字母。

`cohesion_type` 只能使用：

```text
pronoun_reference
logical_connector
lexical_repetition
semantic_contrast
```

## 五、每道题的公共字段

除题型专项字段外，每题必须包含：

```json
{
  "stem": "题干",
  "options": ["选项1", "选项2", "选项3", "选项4"],
  "answer": "选项2",
  "explanation": "中文解析至少三句。说明正确答案依据。说明错误类型。说明两个主要干扰项为什么错误。",
  "knowledge_points": ["学生可理解的中文知识点"],
  "grammar_tags": ["articles"],
  "book_source": "选必一 U1",
  "difficulty": 2
}
```

要求：

- `knowledge_points` 必须是非空、不重复、学生能读懂的中文；
- 不得写 `team_noun`、`material_noun` 等内部 key；
- `grammar_tags` 必须有 1–2 个且不重复；
- `difficulty` 必须是 1–5 的整数；
- `book_source` 必须落在唯一册次；
- `explanation` 至少三句中文，最后必须明确说出两个主要干扰项为什么错误；
- 所有答案必须唯一、无歧义。

## 六、21 个合法 grammar ID

只能使用：

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

不得发明 grammar ID，不得使用选必三、选必四独有语法。

## 七、册次交集规则

题目 `book_source` 解析出的册次，必须属于该题全部 `grammar_tags` 允许册次的交集。

| grammar ID | 允许册次 |
|---|---|
| `relative_clauses_defining` | `{必修}` |
| `relative_clauses_non_defining` | `{必修, 选必一, 跨册}` |
| `passive_voice_tenses` | `{必修, 选必二}` |
| `past_participle_nonfinite` | `{必修}` |
| `v_ing_nonfinite` | `{必修, 选必一, 跨册}` |
| `noun_clauses` | `{必修, 选必一, 选必二, 跨册}` |
| `adverbial_clauses` | `{必修}` |
| `subjunctive_basic_if` | `{选必一, 选必二, 跨册}` |
| `subjunctive_basic_should` | `{选必一, 选必二, 跨册}` |
| `partial_inversion_basic` | `{选必二}` |
| `cleft_basic` | `{必修, 选必一, 跨册}` |
| `tense_system` | `{必修, 选必一, 选必二, 跨册}` |
| `subject_verb_agreement` | `{必修}` |
| `articles` | `{必修}` |
| `prepositions` | `{必修}` |
| `pronouns` | `{必修}` |
| `conjunctions` | `{必修}` |
| `word_formation` | `{必修, 选必一, 选必二, 跨册}` |
| `comparatives_superlatives` | `{必修}` |
| `with_compound` | `{必修, 选必一, 跨册}` |
| `infinitive_nonfinite` | `{必修}` |

如果两个 grammar tag 的允许册次交集为空，该题不能存在。

## 八、全库数量

整个 `m2-bank.json` 必须是：

```text
47 篇 / 300 题
完形填空：6 篇 × 15 = 90
语法填空：6 篇 × 10 = 60
阅读理解：25 篇 × 4 = 100
七选五：10 篇 × 5 = 50
```

`bank.passage_count` 必须等于 `passages.length`。
`bank.question_count` 必须等于所有 `questions.length` 之和。

## 九、全库难度和覆盖

难度分布必须为：

```text
1档 45 题
2档 90 题
3档 105 题
4档 45 题
5档 15 题
```

完形 + 语法的册次分布：

```text
选必二 68 题
选必一 45 题
必修 30 题
跨册 7 题
```

阅读 + 七选五的选必一、选必二话题题合计不少于 75 题。

语法覆盖：

```text
relative_clauses_defining 3
relative_clauses_non_defining 3
passive_voice_tenses 3
past_participle_nonfinite 3
v_ing_nonfinite 3
noun_clauses 3
adverbial_clauses 3
subjunctive_basic_if 3
subjunctive_basic_should 3
partial_inversion_basic 3
cleft_basic 3
tense_system 3
subject_verb_agreement 3
articles 3
prepositions 3
pronouns 3
conjunctions 3
word_formation 3
comparatives_superlatives 2
with_compound 2
infinitive_nonfinite 2
```

阅读题型分布：

```text
main_idea 20
detail 20
inference 20
vocabulary_in_context 20
purpose_or_attitude 20
```

七选五衔接类型：

```text
pronoun_reference 13
logical_connector 13
lexical_repetition 12
semantic_contrast 12
```

完形高频词必须覆盖用户提供的 45 个词，每个词在全库中恰好出现两次。

## 十、词汇、解析和内容限制

- 使用冻结词表和冻结词形归并规则。
- M2 默认生词率不得超过 3%。
- 不得用普通“高频英语词”概念替代冻结词表。
- 阅读题必须有精确原文证据句。
- 不得出现真实学校、考试名称、学生信息。
- 不得复制原文长串内容作为正确选项。
- 同一篇内不得出现两个依赖同一句的定位题。
- 同一 Bank 内不得出现高度相似语篇或题干。
- 解析必须是中文，并明确分析两个主要干扰项。

## 十一、生成方式

由于 47 篇、300 题内容较大，如果平台支持代码或文件工具，应按以下方式执行：

1. 先在内存或临时文件里建立顶层三个字段；
2. 每次生成少量 passage；
3. 每篇先校验结构和总数；
4. 合并到 `passages[]`；
5. 最后运行 JSON 解析、题量统计和标签检查；
6. 只交付完整的 `m2-bank.json`。

如果平台只能聊天输出且无法可靠完成整个大文件，应明确报告：

```json
{
  "error": "SINGLE_FILE_OUTPUT_LIMIT",
  "message": "Current response cannot reliably emit the complete 47-passage JSON."
}
```

不得输出半份 JSON 并声称完整。

## 十二、最终自检

交付前必须检查：

1. 文件能被标准 JSON 解析器读取；
2. 顶层只有 `schema_version`、`bank`、`passages`；
3. `passages` 正好 47 项；
4. 总题数正好 300；
5. 完形 6 篇、语法 6 篇、阅读 25 篇、七选五 10 篇；
6. 每篇题数精确；
7. 每篇词数符合规则；
8. 占位符完整且不重复；
9. 每个答案唯一匹配选项；
10. 七选五答案都是 A–G 单字母；
11. grammar tag 全部在 21 个 ID 内；
12. 每题书册标签位于 grammar tag 允许册次的交集内；
13. 知识点为中文；
14. 解析至少三句且指出两个主要干扰项；
15. 阅读题有精确原文证据句；
16. 全库难度、册次、题型和 grammar 覆盖达标；
17. 无真实个人信息或受版权保护文本；
18. 文件没有 Markdown 围栏或解释文字。

任何一项不通过，必须修复后重新检查。不得在最终 JSON 后面附加“说明”“注意”或完成报告。
