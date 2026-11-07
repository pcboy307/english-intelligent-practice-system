# 语法 ID 册次白名单与覆盖可达性

状态：M0 冻结候选。

## B. 册次标签规则

- 合法取值仅为 `{必修, 选必一, 选必二, 跨册}`。
- 每道考点题必须携带且只携带一个册次标签。
- 册次按题目计数，不按 `grammar_tags` 数量计数；一题即使有主标签与次标签，也只计
  一次册次。
- 每道语法填空题至少一个主 grammar ID，最多再带一个跨单元次 ID；Coverage 可将
  两个 ID 各计一次题次。

## 21 个 ID 的允许册次集合

| # | grammar ID | 允许册次集合 |
|---:|---|---|
| 1 | `relative_clauses_defining` | `{必修}` |
| 2 | `relative_clauses_non_defining` | `{必修, 选必一, 跨册}` |
| 3 | `passive_voice_tenses` | `{必修}` |
| 4 | `past_participle_nonfinite` | `{必修}` |
| 5 | `v_ing_nonfinite` | `{必修, 选必一, 跨册}` |
| 6 | `noun_clauses` | `{必修, 选必一, 选必二, 跨册}` |
| 7 | `adverbial_clauses` | `{必修}` |
| 8 | `subjunctive_basic_if` | `{选必一, 选必二, 跨册}` |
| 9 | `subjunctive_basic_should` | `{选必一, 选必二, 跨册}` |
| 10 | `partial_inversion_basic` | `{选必二}` |
| 11 | `cleft_basic` | `{必修, 选必一, 跨册}` |
| 12 | `tense_system` | `{必修, 选必一, 选必二, 跨册}` |
| 13 | `subject_verb_agreement` | `{必修}` |
| 14 | `articles` | `{必修}` |
| 15 | `prepositions` | `{必修}` |
| 16 | `pronouns` | `{必修}` |
| 17 | `conjunctions` | `{必修}` |
| 18 | `word_formation` | `{必修, 选必一, 选必二, 跨册}` |
| 19 | `comparatives_superlatives` | `{必修}` |
| 20 | `with_compound` | `{必修, 选必一, 跨册}` |
| 21 | `infinitive_nonfinite` | `{必修}` |

此前未形成独占单元标题的 8 个 ID 已明确：

| grammar ID | 允许册次 |
|---|---|
| `adverbial_clauses` | `{必修}` |
| `articles` | `{必修}` |
| `prepositions` | `{必修}` |
| `pronouns` | `{必修}` |
| `conjunctions` | `{必修}` |
| `subject_verb_agreement` | `{必修}` |
| `comparatives_superlatives` | `{必修}` |
| `word_formation` | `{必修, 选必一, 选必二, 跨册}` |

## C. 400 道语法填空可达性

目标题数：

| 册次 | 可用 ID 数 | 专属 ID 数 | 达到专属覆盖所需最少题数 | 本分布可分配上限 |
|---|---:|---:|---:|---:|
| 选必二 | 6 | 1 | 12 | 180 |
| 选必一 | 9 | 0 | 0 | 120 |
| 必修 | 18 | 11 | 66 | 80 |
| 跨册 | 9 | 0 | 0 | 20 |

计算依据：

- 21 个 ID × 每 ID 至少 12 题 = **252 题次**。
- 每题最多两个 grammar ID，因此 400 题总容量为 **800 题次**。
- 必修专属 11 个 ID 需要 132 题次；每题最多双标签时，至少需要 66 道必修题，未超过
  必修目标 80 题。
- 选必二专属的 `partial_inversion_basic` 需要出现在至少 12 道不同题中，未超过选必二
  目标 180 题。
- 其余 9 个多册 ID 共需 108 题次；扣掉专属占用后仍有 656 题次容量。
- 册次目标 `80 + 120 + 180 + 20 = 400`，每道题只进入一个册次。

结论：**可达**。

机器可复算证据：`qa/evidence/m0/grammar-book-feasibility.json`。
