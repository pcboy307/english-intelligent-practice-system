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
| 2022 课标三级核心表 | 1600 | 1596 | 4 |
| 课标数词/日期/地名/机构/节日补充表 | 164 | 120 | 44 |
| 人教版必修 1-3、选必 1-2 | 1846 | 1510 | 336 |
| 闭合功能词补充 | 5 个新增 | 5 | 0 |
| **去重并集** | — | **3015** | **392** |

完整允许表：3407 项。

V11 预期约 3000 词；3015 比约 3000 高约 0.5%。需求提出时的估算区间为 2500–2850，3015 比上界 2850 高约 5.8%。差异来自实际来源并集，不通过删除已学词强行落入估算区间。

## ECDICT 近似差异

ECDICT `zk` 与官方核心表：

```text
official_single=1596
ecdict_zk=1603
intersection=1320
union=1879
official_only=276
alternative_only=283
Jaccard difference=29.75%
```

结论：`zk` 不能作为生产白名单，只保留为审计参照。

## 抽检

- 20 个初中基础词：全部命中。
- 20 个选必三/四或高考 C/D 篇典型难词：全部排除。
- M1 语篇样例 1：115 个单词分母，未知 0，生词率 0%。
- M1 语篇样例 2：116 个单词分母，未知 0，生词率 0%。

详细数据：`qa/evidence/m0/vocabulary-audit.json`。

## 尚不能提供

- `/admin` 本机/非回环连通性证据依赖 M1 后端代码，M0 阶段为 `N/A：服务尚未实现`。
- 手机同一 Wi-Fi 访问学生接口依赖 M1 服务，M0 阶段为 `N/A：服务尚未实现`。
