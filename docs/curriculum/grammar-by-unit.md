# 逐单元语法清单（25 单元）

状态：M0 冻结候选。事实源为 `contracts/curriculum.json`；本表用于说明教材对齐与白名单差异。

## 口径

- 教材正式教学单元共 25 个：必修 1–3 各 5 个，选择性必修 1–2 各 5 个。
- 本表正好 25 行。必修一 Welcome Unit 的词汇属于已学词汇，但不计入 25 个正式题材/语法对齐单元。
- 语法白名单按 **grammar item ID** 计数，不按单元数计数；同一语法项目可出现在多个单元。
- 词汇白名单按 **规范化词元** 计数，不按单元数计数，详见 `contracts/vocabulary-whitelist.json`。
- 单元中若出现白名单外结构，只能在语篇中作为自然语言现象，不得出题考查。
- 选择性必修第三、第四册一律不进入可考范围。

## 清单

| # | 单元 | 题材 | 可考语法项目 ID | 说明 |
|---:|---|---|---|---|
| 1 | 必修一 U1 | 青少年生活与成长 | `pronouns`, `articles`, `subject_verb_agreement`, `word_formation` | 名词/形容词/副词短语只作自然语言，不单独出结构辨析题 |
| 2 | 必修一 U2 | 旅行与计划 | `tense_system`, `adverbial_clauses`, `prepositions` | 现在进行表将来置于基础时态体系内 |
| 3 | 必修一 U3 | 运动与健康 | `comparatives_superlatives`, `subject_verb_agreement`, `conjunctions` | 附加疑问句不属当前白名单，不出题 |
| 4 | 必修一 U4 | 自然灾害与应对 | `relative_clauses_defining`, `past_participle_nonfinite`, `tense_system` | 限制性定语从句只考基础关系词与关系副词 |
| 5 | 必修一 U5 | 世界语言与文字 | `relative_clauses_defining`, `relative_clauses_non_defining`, `word_formation` | 非限制性定语从句采用基础形式 |
| 6 | 必修二 U1 | 文化遗产保护 | `relative_clauses_non_defining`, `passive_voice_tenses` | 不考复杂句法嵌套 |
| 7 | 必修二 U2 | 野生动植物保护 | `passive_voice_tenses`, `tense_system`, `subject_verb_agreement` | 被动语态限于基础时态，含现在进行/现在完成被动 |
| 8 | 必修二 U3 | 互联网与科技生活 | `passive_voice_tenses`, `adverbial_clauses`, `word_formation` | 常考现在完成被动 |
| 9 | 必修二 U4 | 历史与传统 | `past_participle_nonfinite`, `relative_clauses_defining`, `articles` | 过去分词作定语/状语/宾补 |
| 10 | 必修二 U5 | 音乐与艺术 | `past_participle_nonfinite`, `v_ing_nonfinite`, `with_compound` | `with` 结构仅基础形式 |
| 11 | 必修三 U1 | 节日与庆典 | `v_ing_nonfinite`, `relative_clauses_defining`, `pronouns` | `-ing` 作定语、状语、宾补、主语和表语 |
| 12 | 必修三 U2 | 品德与美德 | `v_ing_nonfinite`, `adverbial_clauses`, `conjunctions` | 不考独立主格 |
| 13 | 必修三 U3 | 多元文化 | `noun_clauses`, `adverbial_clauses`, `tense_system` | 名词性从句覆盖宾/表/主/同位语基础形式 |
| 14 | 必修三 U4 | 太空探索 | `cleft_basic`, `noun_clauses`, `passive_voice_tenses` | 强调句仅 `it is/was ... that` 基础形式 |
| 15 | 必修三 U5 | 金钱与价值观 | `noun_clauses`, `subject_verb_agreement`, `articles` | 省略与替代只作自然语言现象 |
| 16 | 选必一 U1 | 杰出人物与成就 | `relative_clauses_non_defining`, `cleft_basic`, `word_formation` | 不考强调句与倒装复合变体 |
| 17 | 选必一 U2 | 未来科技与生活 | `tense_system`, `passive_voice_tenses`, `adverbial_clauses` | 含将来进行与基础将来被动 |
| 18 | 选必一 U3 | 自然公园与旅游 | `v_ing_nonfinite`, `with_compound`, `prepositions` | 不考悬垂分词的高阶辨析 |
| 19 | 选必一 U4 | 肢体语言与非言语沟通 | `v_ing_nonfinite`, `adverbial_clauses`, `pronouns` | 状语从句限于基础类型 |
| 20 | 选必一 U5 | 农业与土地 | `noun_clauses`, `subject_verb_agreement`, `articles` | 多重从句嵌套只作自然语言 |
| 21 | 选必二 U1 | 科学与科学家 | `noun_clauses`, `tense_system`, `word_formation` | 名词性从句侧重表语/宾语基础形式 |
| 22 | 选必二 U2 | 跨文化沟通 | `noun_clauses`, `adverbial_clauses`, `conjunctions` | 不考高阶省略与替代综合判断 |
| 23 | 选必二 U3 | 饮食与文化 | `tense_system`, `passive_voice_tenses`, `past_participle_nonfinite` | 含过去完成与基础完成被动 |
| 24 | 选必二 U4 | 长途旅行与地理 | `partial_inversion_basic`, `tense_system`, `relative_clauses_non_defining` | 倒装仅否定词前置、only+状语、so/neither |
| 25 | 选必二 U5 | 急救与安全 | `subjunctive_basic_if`, `subjunctive_basic_should`, `adverbial_clauses` | 虚拟仅三种 if 时态与 should 型宾语从句 |

## 与教材/需求的差异处理

| 项目 | 处理 |
|---|---|
| 单元中出现的名词短语、形容词短语、副词短语 | 白名单没有独立考查项，只作自然语言，不出结构辨析 |
| 附加疑问句 | 只作自然语言，不出题 |
| 不定式作宾语/状语等单元现象 | 当前白名单未列独立考查项，只作自然语言 |
| 省略、替代、独立主格 | 明确禁止作为考点 |
| 混合/错综时间/含蓄条件/倒装式虚拟 | 明确禁止作为考点 |
| 完全倒装及强调句复合变体 | 明确禁止作为考点 |
| 选必三、选必四独有语法 | 一律禁止，即使语篇自然出现也不得设为考点 |

## M0 签字规则

签字后 `grammar_whitelist` 的 ID 集合冻结。后续若新增语法项目，必须由 Lead 同时更新 `curriculum.json`、本题库校验器、测试夹具和 `CHANGELOG.md`，并经系统所有者批准。
