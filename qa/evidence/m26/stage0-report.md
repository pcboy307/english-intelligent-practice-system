# M2.6 阶段0 定性报告

日期：2026-11-08

## 结论

**情况A：数据错误。** 语篇存储原文把答案词保留在编号空位上，
渲染层只是原样打印该文本，没有额外插入答案。

## 数据库与取证范围

- PostgreSQL：`127.0.0.1:15432`
- 数据库：`english_practice`
- `practice_sessions`：1234 行
- active bank：`6fab59cd-c1fa-4a7a-8532-41bde57d18f2`
- 答案文本逐题检查：150 题

## 直接证据

`M2-FULL-CLOZE-04` 的存储原文如下（节选；完整原文见 JSON）：

```text
Last term, the student faced a new digital learning platform（平台）（平台）for the first time. She felt (1) anxious because she could not follow the online lessons at first. Her teacher told her that anyone could become (2) confident with daily practice. A classmate, who was always (3) curious about new apps, showed her how to use the search tool. The platform（平台） was not always (4) reliable, so the student learned to save her work often. If she were more (5) ambitious, she would try the extra tasks every week. Only by pl
```

15 个编号空位的存储词与该题答案逐一相同：

| 题号 | 答案 | 空位存储词 |
| --- | --- | --- |
| `M2-FULL-CLOZE-04-Q01` | `anxious` | `anxious` |
| `M2-FULL-CLOZE-04-Q02` | `confident` | `confident` |
| `M2-FULL-CLOZE-04-Q03` | `curious` | `curious` |
| `M2-FULL-CLOZE-04-Q04` | `reliable` | `reliable` |
| `M2-FULL-CLOZE-04-Q05` | `ambitious` | `ambitious` |
| `M2-FULL-CLOZE-04-Q06` | `achieve` | `achieve` |
| `M2-FULL-CLOZE-04-Q07` | `adapt` | `adapt` |
| `M2-FULL-CLOZE-04-Q08` | `encourage` | `encouraged` |
| `M2-FULL-CLOZE-04-Q09` | `persuade` | `persuaded` |
| `M2-FULL-CLOZE-04-Q10` | `concentrate` | `concentrated` |
| `M2-FULL-CLOZE-04-Q11` | `gradually` | `gradually` |
| `M2-FULL-CLOZE-04-Q12` | `eventually` | `eventually` |
| `M2-FULL-CLOZE-04-Q13` | `independently` | `independently` |
| `M2-FULL-CLOZE-04-Q14` | `confidence` | `confidence` |
| `M2-FULL-CLOZE-04-Q15` | `opportunity` | `opportunity` |

渲染路径：`apps/mobile/app/practice.tsx:377`

```tsx
<Text style={styles.passage}>{item.passage}</Text>
```

落库路径：`scripts/run-m2-full.py:433`

```python
"passage": str(data.get("passage", "")),
```

生成结果被原样写入，管线中没有“答案词替换为统一占位符”的步骤。

## 影响面

对完形和语法填空共 150 题逐题检查；七选五的 `answer` 是
选项字母，不是可检查的答案文本，因此只统计其占位符形态。

| 口径 | 空数 | 篇数 |
| --- | ---: | ---: |
| 答案直接占据自己的编号空位 | 15 | 1 |
| 答案词或其屈折形式出现在全文任意位置 | 38 | 8 |
| 编号后直接跟普通单词、无下划线占位符 | 89 | 9 |

“全文任意位置”包含语法填空中 `the/of/that/is` 等功能词的
正常复现，不能全部视为答案泄露；直接坏空位只有下面 1 篇。

### 答案直接占据本空位

| 语篇 | 题型 | 空数 |
| --- | --- | ---: |
| `M2-FULL-CLOZE-04` | `cloze` | 15 |

### 答案词在全文任意位置出现

| 语篇 | 题型 | 空数 | 题号与答案 |
| --- | --- | ---: | --- |
| `M2-FULL-CLOZE-04` | `cloze` | 15 | `M2-FULL-CLOZE-04-Q01`=anxious, `M2-FULL-CLOZE-04-Q02`=confident, `M2-FULL-CLOZE-04-Q03`=curious, `M2-FULL-CLOZE-04-Q04`=reliable, `M2-FULL-CLOZE-04-Q05`=ambitious, `M2-FULL-CLOZE-04-Q06`=achieve, `M2-FULL-CLOZE-04-Q07`=adapt, `M2-FULL-CLOZE-04-Q08`=encourage, `M2-FULL-CLOZE-04-Q09`=persuade, `M2-FULL-CLOZE-04-Q10`=concentrate, `M2-FULL-CLOZE-04-Q11`=gradually, `M2-FULL-CLOZE-04-Q12`=eventually, `M2-FULL-CLOZE-04-Q13`=independently, `M2-FULL-CLOZE-04-Q14`=confidence, `M2-FULL-CLOZE-04-Q15`=opportunity |
| `M2-FULL-CLOZE-06` | `cloze` | 1 | `M2-FULL-CLOZE-06-Q08`=choice |
| `M2-FULL-GRAMMAR-01` | `grammar_fill` | 1 | `M2-FULL-GRAMMAR-01-Q10`=tested |
| `M2-FULL-GRAMMAR-02` | `grammar_fill` | 6 | `M2-FULL-GRAMMAR-02-Q01`=chosen, `M2-FULL-GRAMMAR-02-Q02`=encouraged, `M2-FULL-GRAMMAR-02-Q03`=Running, `M2-FULL-GRAMMAR-02-Q04`=Hearing, `M2-FULL-GRAMMAR-02-Q05`=Finishing, `M2-FULL-GRAMMAR-02-Q07`=that |
| `M2-FULL-GRAMMAR-03` | `grammar_fill` | 2 | `M2-FULL-GRAMMAR-03-Q03`=had, `M2-FULL-GRAMMAR-03-Q10`=that |
| `M2-FULL-GRAMMAR-04` | `grammar_fill` | 4 | `M2-FULL-GRAMMAR-04-Q01`=It, `M2-FULL-GRAMMAR-04-Q03`=that, `M2-FULL-GRAMMAR-04-Q07`=is, `M2-FULL-GRAMMAR-04-Q08`=am |
| `M2-FULL-GRAMMAR-05` | `grammar_fill` | 6 | `M2-FULL-GRAMMAR-05-Q01`=The, `M2-FULL-GRAMMAR-05-Q02`=The, `M2-FULL-GRAMMAR-05-Q03`=on, `M2-FULL-GRAMMAR-05-Q06`=of, `M2-FULL-GRAMMAR-05-Q09`=so, `M2-FULL-GRAMMAR-05-Q10`=of |
| `M2-FULL-GRAMMAR-06` | `grammar_fill` | 3 | `M2-FULL-GRAMMAR-06-Q03`=teaching, `M2-FULL-GRAMMAR-06-Q05`=most, `M2-FULL-GRAMMAR-06-Q06`=working |

### 占位符形态错误

| 语篇 | 题型 | 无下划线空位 |
| --- | --- | ---: |
| `M2-FULL-CLOZE-03` | `cloze` | 15 |
| `M2-FULL-CLOZE-04` | `cloze` | 15 |
| `M2-FULL-CLOZE-05` | `cloze` | 15 |
| `M2-FULL-GAP-03` | `gap_fill` | 5 |
| `M2-FULL-GAP-05` | `gap_fill` | 5 |
| `M2-FULL-GAP-06` | `gap_fill` | 5 |
| `M2-FULL-GRAMMAR-03` | `grammar_fill` | 10 |
| `M2-FULL-GRAMMAR-05` | `grammar_fill` | 9 |
| `M2-FULL-GRAMMAR-06` | `grammar_fill` | 10 |

## 处置结论

- 旧库填空类生成数据不可复用。
- M2.6 必须采用“先定答案词、写文时禁词、逐空替换为统一下划线
  占位符、落库前逐题复核”的新管线。
- 本阶段未创建新 bank、未改名旧 bank、未生成任何 Stage A 内容。
