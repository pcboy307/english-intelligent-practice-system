# 语法 ID 归属规则

状态：M0 冻结候选。

`contracts/curriculum.json` 共有 21 个语法 ID。25 单元表直接归属其中 8 个：

```text
relative_clauses_defining
relative_clauses_non_defining
passive_voice_tenses
past_participle_nonfinite
v_ing_nonfinite
noun_clauses
tense_system
infinitive_nonfinite
```

其余 13 个 ID 没有在 25 个单元的 `Structures` 板块中形成独占标题。它们按下列规则归属，不强行绑定到某个单元，也不因“没有独占单元”而视为白名单外。
完整 21 个 ID 的册次矩阵见 `docs/curriculum/grammar-book-matrix.md`。

## 13 个跨单元 ID

| # | grammar ID | 允许册次集合 | 归属规则 |
|---:|---|---|---|
| 1 | `adverbial_clauses` | `{必修}` | 跨单元高频语法；仅当题目文本、语法标签和出处三者一致时可作主标签 |
| 2 | `subjunctive_basic_if` | `{选必一, 选必二, 跨册}` | 只归属基础 if 虚拟；混合、含蓄、倒装虚拟不得借用此 ID |
| 3 | `subjunctive_basic_should` | `{选必一, 选必二, 跨册}` | 只归属建议/要求/命令类 should 型宾语从句 |
| 4 | `partial_inversion_basic` | `{选必二}` | 只归属否定词前置、only+状语、so/neither 三类基础部分倒装 |
| 5 | `cleft_basic` | `{必修, 选必一, 跨册}` | 只归属 `it is/was ... that` 基础强调句；不归属强调与倒装复合 |
| 6 | `subject_verb_agreement` | `{必修}` | 按教材实际语篇/练习出处归属；不得只凭题干含谓语就自动打标 |
| 7 | `articles` | `{必修}` | 按实际考点归属；冠词只作自然语言出现时不打语法考点标签 |
| 8 | `prepositions` | `{必修}` | 按实际考点归属；固定搭配中的介词须与知识点一并记录 |
| 9 | `pronouns` | `{必修}` | 按实际考点归属；七选五代词衔接只使用七选五衔接标签时可并列记录 |
| 10 | `conjunctions` | `{必修}` | 按实际考点归属；七选五逻辑连接词须同时记录衔接类型 |
| 11 | `word_formation` | `{必修, 选必一, 选必二, 跨册}` | 只有题目实际考查前后缀或词性转换时才归属；生词释义不自动计作构词法考点 |
| 12 | `comparatives_superlatives` | `{必修}` | 只归属比较级、最高级、`as...as`、`the more...the more` |
| 13 | `with_compound` | `{必修, 选必一, 跨册}` | 只归属基础 with 复合结构；独立主格不得借用此 ID |

## 打标优先级

1. 单元 `Structures` 板块有独占标题时，8 个直接归属 ID 为主标签。
2. 13 个跨单元 ID 可作为主标签或次标签，但必须能引用题目所对应的教材册次与实际语言现象。
3. 同一题至少有一个主标签，最多再有一个跨单元次标签；Coverage 按实际 ID 题次计。
4. 无法追溯到 V11 教材范围的标签不得落库。
5. 13 个 ID 的 Coverage 出口与其他 ID 相同：语法填空全库中每个 ID 至少 12 题，否则标红。
6. 每道题必须且只能有一个册次标签；册次只按题目计一次，不受 grammar tag 数量影响。

## 数量校验

```text
全部 grammar ID = 21
25 单元直接归属 = 8
跨单元归属 = 13
8 + 13 = 21
```
