# M0 契约审核记录

状态：待系统所有者签字，未冻结。

## 已完成的机械验证

```text
python scripts/check-m0.ps1
M0_CHECK=PASS

npx @apidevtools/swagger-cli validate contracts/openapi.yaml
contracts/openapi.yaml is valid

python scripts/vocabulary-audit.py ...
checks_pass=true
```

## 词汇三层计数

| 层 | 去重前/官方声明 | 单词头 | 短语 |
|---|---:|---:|---:|
| 2022 课标三级核心表 | 声明 1600 项；斜杠变体展开为 1607 个匹配形式 | 1603 | 4 |
| 课标数词/日期/地名/机构/节日补充表 | 164 | 120 | 44 |
| 人教版必修 1-3、选必 1-2 | 1846 | 1510 | 336 |
| 闭合功能词补充 | 5 个新增 | 5 | 0 |
| **去重并集** | — | **3021** | **392** |

完整允许表：3413 项。

V11 预期约 3000 词；3021 比约 3000 高约 0.7%。需求提出时的估算区间为 2500–2850，3021 比上界 2850 高约 6.0%。差异来自实际来源并集，不通过删除已学词强行落入估算区间。

## ECDICT 近似差异

ECDICT `zk` 与官方核心表：

```text
official_single=1603
ecdict_zk=1603
intersection=1326
union=1880
official_only=277
alternative_only=277
Jaccard difference=29.47%
```

结论：`zk` 不能作为生产白名单，只保留为审计参照。

## 抽检

- 20 个初中基础词：全部命中。
- 20 个选必三/四或高考 C/D 篇典型难词：全部排除。
- 人教版必修一 U1 “First Impressions”：200 个单词分母，未知 0，生词率 0%。这是教材来源原文，0% 符合“教材词表覆盖教材文本”的预期。
- 2025 年 3 月精诚联盟高二 Text B 首段真实素材：82 个单词分母，未知 `burrito` 2 次，生词率 **2.44%**，在 0–3% 上限内；该校外专有名词 `Milpitas` 按来源元数据排除。

详细数据：`qa/evidence/m0/real-source-vocabulary-audit.json`。

## 统计口径

本表按教材词表口径统计“教材实际列出的词”，宽于课标最低要求，生词率判定偏宽松；超纲校验以“高阶难词抽检被排除”和“语法标签全部在白名单”为准，不以生词率单指标判定。

## 尚不能提供

- `/admin` 本机/非回环连通性证据依赖 M1 后端代码，M0 阶段为 `N/A：服务尚未实现`。
- 手机同一 Wi-Fi 访问学生接口依赖 M1 服务，M0 阶段为 `N/A：服务尚未实现`。

## 执行方式

多 Agent 并行不可用，已按 CO-002 改为严格串行。实际执行方式与 V11 多 Agent 要求存在偏差，详见 `docs/change-log/CO-002-serial-execution.md`；该偏差不改变 M1 验收范围。
