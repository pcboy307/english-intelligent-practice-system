# 语法白名单映射

状态：M0 冻结候选。

| V11 1.2-B 行 | V11 原文类别 | `contracts/curriculum.json` ID |
|---:|---|---|
| 1 | 定语从句：关系代词、关系副词、非限制性 | `relative_clauses_defining`, `relative_clauses_non_defining` |
| 2 | 被动语态各时态 | `passive_voice_tenses` |
| 3 | 过去分词作定语、状语、宾补 | `past_participle_nonfinite` |
| 4 | 动词 -ing 作定语、状语、宾补、主语 | `v_ing_nonfinite` |
| 5 | 名词性从句：宾、表、主、同位语 | `noun_clauses` |
| 6 | 状语从句：时间、条件、让步、原因、结果、目的、比较 | `adverbial_clauses` |
| 7 | 基础虚拟语气 | `subjunctive_basic_if`, `subjunctive_basic_should` |
| 8 | 基础部分倒装 | `partial_inversion_basic` |
| 9 | 基础强调句 | `cleft_basic` |
| 10 | 时态体系 | `tense_system` |
| 11 | 主谓一致、冠词、介词、代词、连词 | `subject_verb_agreement`, `articles`, `prepositions`, `pronouns`, `conjunctions` |
| 12 | 构词法 | `word_formation` |
| 13 | 比较级、最高级、as...as、the more...the more | `comparatives_superlatives` |
| 14 | 基础 with 复合结构 | `with_compound` |
| 15 | 基础不定式 | `infinitive_nonfinite` |

## 聚合 ID 的授权子项集合 S

| grammar ID | 授权子项集合 S |
|---|---|
| `v_ing_nonfinite` | `{作定语, 作状语, 作宾补, 作主语}` |
| `infinitive_nonfinite` | `{作宾语, 作表语, 作目的状语, 作结果状语, 作定语, 作主语}` |
| `past_participle_nonfinite` | `{作定语, 作状语, 作宾补}` |
| `relative_clauses_defining` | `{关系代词, 关系副词}` |
| `tense_system` | `{一般现在时, 一般过去时, 一般将来时, 现在完成时, 过去完成时, 现在进行时, 过去进行时, 将来进行时}` |
| `noun_clauses` | `{宾语从句, 表语从句, 主语从句, 同位语从句}` |
| `passive_voice_tenses` | `{一般现在时被动, 一般过去时被动, 一般将来时被动, 现在完成时被动, 过去完成时被动, 现在进行时被动, 过去进行时被动, 将来进行时被动}` |

设教材实际语法子项集合为 T，判定规则：

| 集合关系 | 差异类型 |
|---|---|
| `T = S` | 完全一致 |
| `T ⊂ S` 且非空 | 教材范围更窄 |
| `T` 含 `S` 以外子项 | 教材范围更宽 |
| `T ∩ S = ∅` | 白名单外 |

V11 第 4 行原文（需求文件第 81 行）：

```text
| 动词 -ing 作定语 / 状语 / 宾补 / 主语 | 必修三、选必一 |
```

原文没有“作宾语”。因此 `v_ing_nonfinite` 的授权集合不扩权，选必一 U4 只能
开放作状语，禁止设题：作宾语、作表语。

## 项目总数解释

当前版本共 15 行。原 V11 14 行按最小项目拆分时为 18 项；新增基础不定式后为 19 项。

当前有 21 项，另外 2 项仅因以下两行被拆得更细：

1. 第 1 行拆为 `relative_clauses_defining` 与 `relative_clauses_non_defining`，新增 1 项。
2. 第 7 行拆为 `subjunctive_basic_if` 与 `subjunctive_basic_should`，新增 1 项。

因此 21 项全部在当前版本授权范围内，没有新增白名单外语法。
