# 高二英语智能练习系统

面向广东省高二学生的人教版（2019）英语智能练习系统。系统包含 React Native + Expo 学生端、FastAPI 后端、PostgreSQL、Redis，以及题库生成与审核管线。

## 项目状态

当前处于 **M0 契约冻结**。M0 通过审核并签字前不得进入 M1 业务实现。

## 锁定运行时

| 组件 | 版本 | 说明 |
|---|---|---|
| Node.js | 24.x LTS | Expo SDK 58 官方 engines 支持 `^24.3.0`；不直接使用宿主机的 Node 26 |
| npm | 11.x | 与锁定 Node 版本配套 |
| Python | 3.12.x | 使用稳定 wheel，不使用宿主机 Python 3.15 |
| Expo SDK | 58 | React Native 学生端 |
| PostgreSQL | 16.x | 本地 Docker Compose |
| Redis | 7.x | 本地 Docker Compose |

切换版本：

```bash
nvm use
pyenv install 3.12
pyenv local 3.12
```

Windows 若未安装 nvm/pyenv，请分别安装 Node 24 LTS 与 Python 3.12，并确认：

```bash
node --version
python --version
```

## 开发原则

- `contracts/`、`config/`、`db/migrations/` 与根脚本只由 Lead Agent 维护。
- 每个任务一次 commit；每个里程碑打一个 tag 并提交独立验收记录。
- 所有设计取值来自 `contracts/design-tokens.json`，学生端与后台代码不得硬编码颜色、字号或间距。
- 题库按独立 Bank 管理，禁止跨 Bank 混抽、覆盖或向已存在 Bank 追加题目。
- 交卷前答案与解析不得进入 API 响应或 App 持久化。
- 后端监听 `0.0.0.0`；`/admin/*` 只接受本机回环来源和 `X-Admin-Token`。

## 启动

启动步骤将在 M1 工程完成后补齐。M0 只冻结契约与文档，尚不能运行应用。
