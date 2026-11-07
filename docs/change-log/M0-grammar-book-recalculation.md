# M0 语法集合与册次重算

日期：2026-11-07

状态：等待所有者复核 A/B/C；版本保持 V11.5。

## A. 25 单元集合重判

- 为 7 个聚合 ID 建立授权子项集合 S。
- 25 单元按 `T=S`、`T⊂S`、`T` 含越界项、`T∩S=∅` 四档重判。
- 变化：第 5、6、9、10、12、14、23 行由“完全一致”改为“教材范围更窄”。
- 第 19 行按 V11 原文重写处置：只开放作状语，禁止作宾语、作表语。
- 新计数：完全一致 2、教材范围更窄 18、教材范围更宽 2、白名单外 3。

## B. 册次白名单

- 为 21 个 grammar ID 写明允许册次集合，合法值为 `必修/选必一/选必二/跨册`。
- `passive_voice_tenses` 修正为 `{必修, 选必二}`，消除第 23 行矛盾。
- 每道题增加单一 `book_tag` 字段；主、次 grammar tag 不增加册次计数。
- question、session、report 与 OpenAPI review schema 同步。
- 25 行册次一致性机械自检：25 行检查、0 处不匹配。

## C. 400 题可达性

- 21 个 ID × 12 题 = 252 题次。
- 210 个 ID 对中，176 对存在共同册次、34 对交集为空。
- 同一册次内的两个可用 ID 必然兼容，因此每题双标签能力不因 34 个跨册空交集降低。
- 兼容对覆盖见证：132 道题完成 252 题次覆盖，未超过 `80/120/180/20` 配额。
- 结论：可达。

证据：`qa/evidence/m0/grammar-book-feasibility.json`。

## D. 双标签校验器

- 新增 `backend/app/question_validation.py`。
- 对全部 grammar tag 的允许册次求交集，要求唯一 `book_tag` 属于交集。
- 空交集或标签不在交集时返回 `BOOK_TAG_INCOMPATIBLE`，并输出冲突 ID 与允许册次。
- 单标签题使用相同路径。
- 两个 `partial_inversion_basic + articles` 空交集样例均拒收；
  `tense_system + articles / 选必二` 在交集非空但册次不在交集时拒收，reason
  为 `BOOK_TAG_NOT_IN_INTERSECTION`；合法
  `tense_system + noun_clauses / 选必二` 样例通过。

原始输出：`qa/evidence/m0/book-tag-compatibility.json`。
