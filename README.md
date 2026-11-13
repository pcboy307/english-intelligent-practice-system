# 高二英语智能练习系统

面向广东省高二学生的人教版（2019）英语智能练习系统。系统包含 React Native + Expo 学生端、FastAPI 后端、PostgreSQL、Redis，以及题库生成与审核管线。

## 项目状态

当前 active Bank 为 **`20261109_500`**，包含 **72 篇 / 500 题**。
早期 47 篇 / 300 题的 `M2 Bank #2` 与 M1 Demo Bank 均作为历史交付保留；
当前运行题库以实时 API 和数据库为准。

M0 契约与 M1 验收已于 2026-11-07 签字通过；M1 的 80 题 Demo Bank
现作为历史归档保留。`M2-status.md` 保留为 300 题阶段的历史记录。

当前需求版本严格读取 `contracts/VERSION`，并与 `contracts/curriculum.json.requirement_version` 机械校验。本期运行载体为 **Expo Web（react-native-web）电脑浏览器**。React Native 源码保留，手机真机验收推迟到手机端阶段，不作为本期门禁。

V11.3 的练习页按篇分节，语法填空使用语篇后四选一；报告与答题回顾支持双向跳转。

V11.4 将练习页改为逐题展示，新增本地模型薄弱点分析、历史报告列表与删除能力。

V11.5 将交卷确认改为弹窗，并支持退出未交卷练习且不保留本次题目和报告。

## 项目复盘与技术资产

- 项目全周期总结：`docs/project-retrospective-2026-11-09.md`
- 当前系统架构与限制：`docs/architecture/system-overview.md`
- 可复用提示词模板库：`docs/prompt-library/README.md`
- 项目专用 Skill：`skills/high-school-english-content-ops/SKILL.md`

## Windows 安装包

当前可生成免管理员、自包含 Windows x64 安装器：

```text
dist/windows/GaoerEnglishPractice-Setup.exe
```

安装包包含 Expo Web、FastAPI、便携 Python 3.12、PostgreSQL 16 和当前
`20261109_500` 题库。用户无需安装 Node、Python、Docker 或 PostgreSQL。

详细说明：

- 构建：`docs/windows-installer-build.md`
- 安装：`docs/windows-installer-user-guide.md`
- 验收：`docs/milestones/windows-installer-acceptance.md`

## 题库生成与评审

大模型生成题库、评审导出题库或修改后重新导入时，唯一有效标准为：

```text
docs/question-bank-generation-standard-v2.md
```

该文件同时定义 `bank-v1` / `m26-v1` 格式、72 篇 / 500 题配额、
M2.6 质量门禁、导出评审模式和最终自检。

## 锁定运行时

| 组件 | 版本 | 说明 |
|---|---|---|
| Node.js | 24.x LTS | Expo SDK 58 官方 engines 支持 `^24.3.0`；不直接使用宿主机的 Node 26 |
| npm | 11.x | 与锁定 Node 版本配套 |
| Python | 3.12.x | 使用稳定 wheel，不使用宿主机 Python 3.15 |
| Expo SDK | 58 | React Native 学生端 |
| Expo Web | SDK 58 配套版本 | 本期电脑浏览器运行载体 |
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
- 后端监听 `0.0.0.0`；`/admin/*` 默认只接受本机回环来源和 `X-Admin-Token`。
- 题库切换和 maintenance 接口只接受本机回环来源，不要求口令。
- Web 端 `device_student_id` 暂存 localStorage；这是本地演示安全降级，回到手机端必须换回 secure store。

## 端口与 CORS

| 服务 | 地址 |
|---|---|
| FastAPI | `http://localhost:8000` |
| Expo Web | `http://localhost:8081` |

CORS 只允许：

```text
http://localhost:8081
http://127.0.0.1:8081
```

不使用 `*`。浏览器页面固定 `color-scheme: light`；桌面内容区最大宽度 960px，正文块 760px；`<768px` 时内容最大宽度回落 480px。

Expo Web 依赖通过 `npx expo install` 固定版本，见 `apps/mobile/package.json`：

```text
react-dom
react-native-web
@expo/metro-runtime
```

## 前端启动

M1 工程完成后只使用以下浏览器启动命令：

```bash
cd apps/mobile
npx expo start --web
```

修改 `contracts/openapi.yaml` 后，在 `apps/mobile` 执行：

```bash
npm run generate:api
```

不再提供手机扫码步骤。后端和 PostgreSQL 可用是 M1 环境门禁；Docker 可用时使用 Compose，不可用时使用本机 PostgreSQL。
