# 高二英语智能练习系统

面向广东省高二学生的人教版（2019）英语智能练习系统。系统包含 React Native + Expo 学生端、FastAPI 后端、PostgreSQL、Redis，以及题库生成与审核管线。

## 项目状态

当前处于 **M0 契约收口**。所有者已用 CO-003 授权半日最小闭环实施；M0 最终细节仍需签字，半日成果不能单独替代 M0/M1 正式验收。

当前需求版本严格读取 `contracts/VERSION`，并与 `contracts/curriculum.json.requirement_version` 机械校验。本期运行载体为 **Expo Web（react-native-web）电脑浏览器**。React Native 源码保留，手机真机验收推迟到手机端阶段，不作为本期门禁。

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
- 后端监听 `0.0.0.0`；`/admin/*` 只接受本机回环来源和 `X-Admin-Token`。
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

不使用 `*`。浏览器页面固定 `color-scheme: light`，内容最大宽度 480px 并水平居中。

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

不再提供手机扫码步骤。后端和 PostgreSQL 可用是 M1 环境门禁；Docker 可用时使用 Compose，不可用时使用本机 PostgreSQL。
