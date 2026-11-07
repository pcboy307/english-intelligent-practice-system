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
| 3 | `passive_voice_tenses` | `{必修, 选必二}` |
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

## 25 行册次一致性自检

逐行读取 `grammar-by-unit.md`，对本行每个 ID 校验：

```text
单元所属册次 ∈ grammar ID 的 allowed_book_tags
```

结果：

```text
检查行数：25
不匹配：0
```

第 23 行曾暴露的 `passive_voice_tenses` 矛盾已修复，该 ID 的允许集合改为
`{必修, 选必二}`。

## C. 双标签兼容性与 400 题可达性

| 册次 | 可用 ID 数 | 专属 ID 数 | 专属覆盖最少题数 | 本分布可分配上限 |
|---|---:|---:|---:|---:|
| 选必二 | 7 | 1 | 12 | 180 |
| 选必一 | 9 | 0 | 0 | 120 |
| 必修 | 18 | 10 | 60 | 80 |
| 跨册 | 9 | 0 | 0 | 20 |

### 210 个 ID 对的交集结果

- 两两组合总数：`C(21,2) = 210`
- 有共同允许册次、可组合：176 对
- 交集为空、不可组合：34 对

34 个不可组合对完整列出如下：

| 固定一侧 ID | 不可组合的另一侧 ID |
|---|---|
| `relative_clauses_defining` | `subjunctive_basic_if`, `subjunctive_basic_should`, `partial_inversion_basic` |
| `relative_clauses_non_defining` | `partial_inversion_basic` |
| `past_participle_nonfinite` | `subjunctive_basic_if`, `subjunctive_basic_should`, `partial_inversion_basic` |
| `v_ing_nonfinite` | `partial_inversion_basic` |
| `adverbial_clauses` | `subjunctive_basic_if`, `subjunctive_basic_should`, `partial_inversion_basic` |
| `subjunctive_basic_if` | `subject_verb_agreement`, `articles`, `prepositions`, `pronouns`, `conjunctions`, `comparatives_superlatives`, `infinitive_nonfinite` |
| `subjunctive_basic_should` | `subject_verb_agreement`, `articles`, `prepositions`, `pronouns`, `conjunctions`, `comparatives_superlatives`, `infinitive_nonfinite` |
| `partial_inversion_basic` | `cleft_basic`, `subject_verb_agreement`, `articles`, `prepositions`, `pronouns`, `conjunctions`, `comparatives_superlatives`, `with_compound`, `infinitive_nonfinite` |

表中每一对都确实交集为空，没有把有共同册次的 ID 误列入。

### 每个册次内的可组合性

同一册次内任意两个可用 ID 都因共同包含该册次而可组合：

| 册次 | 可用 ID 数 | 册内可组合对 | 无法配对而落单的 ID |
|---|---:|---:|---:|
| 必修 | 18 | 153 | 0 |
| 选必一 | 9 | 36 | 0 |
| 选必二 | 7 | 21 | 0 |
| 跨册 | 9 | 36 | 0 |

因此，34 个全局不可组合对不会降低单册次内“两道 grammar tag 共题”的能力。

### 可执行覆盖见证

按兼容对求解出一组 252 题次覆盖见证：

| 册次 | 覆盖用题数 | 覆盖题次 | 本分布可分配上限 |
|---|---:|---:|---:|
| 必修 | 60 | 120 | 80 |
| 选必一 | 24 | 48 | 120 |
| 选必二 | 48 | 84 | 180 |
| 跨册 | 0 | 0 | 20 |
| 合计 | 132 | 252 | 400 |

- 21 个 ID × 每 ID 至少 12 题 = **252 题次**。
- 每题最多两个兼容 grammar ID，400 题总容量仍为 **800 题次**。
- 上述见证只用 132 道题就完成全部 252 题次覆盖，且各册次均未超过目标配额。
- 剩余 268 道题可用任意单标签或兼容双标签的重复题次填充，从而精确达到
  `80/120/180/20`。

结论：**可达**。

机器可复算证据：`qa/evidence/m0/grammar-book-feasibility.json`。该文件包含全部 210
个 ID 对、34 个空交集对、逐册次见证和 25 行一致性检查结果。

## D. 校验器执行规则

`backend/app/question_validation.py` 对每道题执行：

1. 读取全部 `grammar_tags` 的 `allowed_book_tags`；
2. 求交集；
3. 要求该题唯一 `book_tag` 属于交集；
4. 交集为空或标签不在交集时抛 `BOOK_TAG_INCOMPATIBLE`；
5. 单标签题也走同一路径，单 ID 的交集就是它自己的允许册次。

拒收结果携带每个 grammar ID 的允许册次及冲突对。三个固定验收样例：

| grammar_tags | book_tag | 预期 | 结果 |
|---|---|---|---|
| `partial_inversion_basic + articles` | `必修` | 拒收 | `BOOK_TAG_INCOMPATIBLE` |
| `partial_inversion_basic + articles` | `选必二` | 拒收 | `BOOK_TAG_INCOMPATIBLE` |
| `tense_system + noun_clauses` | `选必二` | 通过 | `ok=true` |

原始输出：`qa/evidence/m0/book-tag-compatibility.json`。
