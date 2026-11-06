# 代码所有权与写入边界

| 角色 | 独占可写目录 | 禁止写入 |
|---|---|---|
| A Lead | `contracts/`, `config/`, `db/migrations/`, `docs/`, 根脚本, `.codex/` | B–F 模块实现 |
| B 题库管线 | `services/question_pipeline/`, `admin/` | 组卷、报告、App、契约、配置、迁移 |
| C 练习引擎 | `services/practice/` | 题库生成、报告文案、App、契约、配置、迁移 |
| D 报告分析 | `services/reporting/` | 组卷、判分、App、契约、配置、迁移 |
| E App 端 | `apps/mobile/` | 后端、契约、配置、迁移 |
| F QA | `tests/`, `qa/` | 所有业务代码、契约、配置、迁移 |

## 强制规则

1. 同一模块同一时间只有一个写者。
2. 子 Agent 交付必须附带命令、退出码和输出摘要。
3. 未实现接口只能按 `contracts/openapi.yaml` 和 Schemas 对接，不得口头约定。
4. QA 只提交缺陷、测试和证据，不直接修改业务代码。
5. 每个里程碑一个 commit；跨模块集成由 Lead 完成。
6. 并行上限为 3 个子 Agent；生成 job 永远串行。
7. App 与后台视觉只能读取 `contracts/design-tokens.json`。
