# M1 状态

状态：**已完成**。

阻塞项：**已完成**。

签字日期：**2026-11-07**。

最终验收 commit：`59284d8a97199915c4fe95390dc1a2f576ddd730`。

## 签字声明

M0 契约 与 M1 验收，签字通过。

M0 依据：25 行四档表按集合判据重判（完全一致 2 / 更窄 18 / 更宽 2 / 白名单外 3）；
21 个 ID 册次白名单；25 行册次机械自检 0 不匹配；45/30/20/5 可达性结论「可达」；
双标签不可组合对 34 个已列并落入校验器。

M1 依据：Demo Bank 80 题 11 篇；交卷前 has_answer=false /
has_explanation=false；交卷幂等；跨会话两次消标；门禁三层且 fail-closed。

2026-11-09 用户推翻原组卷规则，当前选题只保留两条：每套选 1 篇完形、
1 篇语法填空、1 篇阅读或七选五，先选择三篇覆盖次数总和最少的组合；并列时优先
覆盖 3 个不同话题。原 tag≤3、册次、难度、权重和并发语篇约束不再参与选题。

已知欠账：全部登记在 `docs/待补齐清单.md`，不阻塞签字。

## M0 A/B/C 交付

- A：25 单元已按集合关系重判，结果 `完全一致 2 / 教材范围更窄 18 /
  教材范围更宽 2 / 白名单外 3`，见 `docs/curriculum/grammar-by-unit.md`。
- B：21 个 ID 已写入允许册次集合；每道题使用唯一 `book_tag`。见
  `docs/curriculum/grammar-book-matrix.md`。
- 25 行册次机械自检：检查 25 行、不匹配 0。
- C：210 个 ID 对中有 34 个空交集、176 个可组合对；兼容对覆盖见证为 132 题、
  252 题次，复算结论为“可达”，见
  `qa/evidence/m0/grammar-book-feasibility.json`。
- D：`BOOK_TAG_INCOMPATIBLE` 校验已实现；两个空交集非法样例和一个非空交集误选
  册次的样例均拒收，一个合法双标签样例通过。非空交集分支使用独立 reason
  `BOOK_TAG_NOT_IN_INTERSECTION`。原始输出见
  `qa/evidence/m0/book-tag-compatibility.json`。
- 以上仍需所有者复核，M1 门禁保持阻塞。

## Demo Bank

- 当前题库：**80 题 / 11 篇**。
- 构成：完形 30 题、语法填空 20 题、阅读 20 题、七选五 10 题。
- 本轮 8 篇 50 题为确定性人工编写，未经过 AI 生成管线；生成管线与校验器的
  端到端验证属于 M3 范围。
- 本轮生成 token：`0`。
- 逐篇词数、题数、21 个 grammar ID、生词率与高阶难词抽检全部通过：
  `qa/evidence/m1/demo-bank-validation.json`。

## 四套连开（两条规则重置后）

当前验收测试连续交卷四套，逐套检查：

| 规则 | 验收方式 |
|---|---|
| 每套 1 篇完形 + 1 篇语法 + 1 篇阅读或七选五 | 校验实际题型集合与 3 个篇 ID |
| 优先覆盖次数少的文章 | 四套均为 `selected_total_passage_coverage_count=0`，且与前套篇 ID 不相交 |
| 覆盖次数并列时优先 3 个不同话题 | 校验话题集合与 `selected_distinct_topic_count` |

测试命令：`.\.venv\Scripts\python.exe -m pytest
tests\api\test_half_day_flow.py::test_four_papers_prioritize_low_coverage_passages
-q`。旧 `qa/evidence/m1/four-rule-decisions.json` 仅保留为历史证据，不再代表
当前选题逻辑。

## 其他验证

- PostgreSQL 原始计数见 `qa/evidence/m1/bank-counts.txt`。
- 薄弱点分析模型为 `qwen3.5:4b-q4_K_M`，通过本机 `llama.cpp` OpenAI 兼容接口
  `127.0.0.1:11435` 部署，服务端为 `llama-server 0.8.0-dev (commit
  39febd2ad)`。
- 实际 LLM 输出 73 字，答题数采用“总题数 + 答对数”表述，包含具体考点、错因和
  以“建议：”开头的动作：
  “29 题中答对 23 题，但三处薄弱点暴露出时态与语态混淆问题。现在完成时易误用
  过去时，因忽视‘对现在影响’；建议：今天重做一组同类题并复述错因。”
  证据见 `qa/evidence/m1/weakness-analysis.json`。
- 强制连接失败时报告仍返回规则版分析，`source=fallback`，输出 66 字：
  `qa/evidence/m1/weakness-analysis-fallback.json`。
- 29 题报告标题和分母使用实际题数；30 题七选五场同理。

## 尚未关闭

- 80 题 Demo 未按全库五档分布（15/30/35/15/5，即 12/24/28/12/4），
  M3 全量 2000 题时必须精确达标。
- M1 最终签字仍需按 V11 第十节 1–11 条逐项交验。
