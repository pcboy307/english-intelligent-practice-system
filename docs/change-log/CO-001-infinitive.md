# CO-001：补入基础不定式

- 日期：2026-11-07
- 决定人：用户
- 变更类型：需求变更
- 版本：V11 → V11.1

## 内容

新增第 15 行语法白名单：基础不定式 `infinitive_nonfinite`。

允许功能：

1. 作宾语
2. 作表语
3. 作目的或结果状语
4. 作定语
5. 作主语

允许形式：

1. 一般式 `to do`
2. 被动式 `to be done`

## 禁止作为考点

1. 完成式 `to have done` / `to have been done`
2. 进行式 `to be doing`
3. 分裂不定式辨析
4. `remember/forget/stop/regret/mean` 后 `to do` 与 `doing` 的意义差异辨析；只能作固定搭配识记
5. `to be honest` 等独立不定式成分

## 连带影响

| 对象 | 结果 |
|---|---|
| 语法白名单 | 14 行 → 15 行 |
| grammar ID | 20 → 21 |
| 必修三 U4 | 白名单外 → 完全一致；只考本单元教材三类功能 |
| 25 单元差异统计 | 完全一致 8→9；范围收窄 13；白名单外 4→3 |
| `question.json` | `grammar_tags` 枚举加入 `infinitive_nonfinite` |
| Coverage | 语法填空每个 grammar ID 至少 12 题 |
| 待补齐清单 | 已标记“V11 白名单缺口 — 基础不定式”为已裁定、已补入 |

## 范围限制

本变更单不调整其他 14 行白名单的范围或拆分粒度。今后发现其他缺口时，另立变更单。
