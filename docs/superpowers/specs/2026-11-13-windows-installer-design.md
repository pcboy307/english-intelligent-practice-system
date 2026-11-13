# Windows 自包含安装器设计

日期：2026-11-13

状态：用户已选择方案 A

目标平台：Windows 10/11 x64

## 1. 目标

生成一个可由普通用户双击安装、无需管理员权限、无需预装 Node/Python/Docker/PostgreSQL 的安装器。安装后通过桌面或开始菜单快捷方式启动系统，在默认浏览器完成练习、报告、历史、错题和题库管理。

## 2. 非目标

- 不支持 Windows ARM64 或 32 位系统。
- 不在本轮申请商业代码签名证书。
- 不将系统改造成纯离线 LLM 应用；DeepSeek/本地模型不可用时仍使用规则降级分析。
- 不允许目标电脑自行修改固定 PostgreSQL 端口和数据库名。

## 3. 交付物

```text
dist/windows/GaoerEnglishPractice-Setup.exe
```

安装目录采用当前用户 `LOCALAPPDATA`，不要求 UAC。用户数据独立保存在：

```text
%LOCALAPPDATA%\GaoerEnglishPractice\data
```

安装升级不应覆盖该目录。

## 4. 打包组成

| 组件 | 来源 | 说明 |
|---|---|---|
| 前端 | `apps/mobile` Expo Web export | `web.output=single`，SPA fallback |
| 后端 | `backend/` | 现有 FastAPI 应用 |
| 配置与契约 | `config/`、`contracts/` | 运行时读取 |
| 数据库迁移 | `db/migrations/` | 首次运行按文件名顺序执行 |
| Python | 本机 Python 3.12 完整运行时 | 复制到安装目录 |
| Python 依赖 | `backend/pyproject.toml` | 安装到便携 Python 的 `Lib/site-packages` |
| PostgreSQL | `C:\pgsql\bin`、`lib`、`share` | 排除 pgAdmin、StackBuilder |
| Seed | 当前 active Bank 导出 JSON | 首次运行导入 |
| 启动器 | `desktop/` | 初始化、启动、停止、打开浏览器 |

## 5. 运行时

固定端口：

- Expo Web 静态服务：`127.0.0.1:8081`
- FastAPI：`0.0.0.0:8000`
- PostgreSQL：`127.0.0.1:15432`
- 数据库名：`english_practice`

首次启动：

1. 检查 LOCALAPPDATA 下是否已有 pgdata。
2. 无数据时执行 `initdb`。
3. 启动 PostgreSQL。
4. 创建 `english_practice`。
5. 执行迁移。
6. 无 active Bank 时导入 seed。
7. 启动 FastAPI。
8. 启动 SPA 静态服务器。
9. 等待健康检查。
10. 打开默认浏览器首页。

后续启动复用数据目录，不重复初始化。

## 6. 进程与日志

- 启动器使用 `pythonw.exe`，不显示控制台。
- 子进程使用无窗口创建标志。
- PID、日志和状态保存在数据目录的 `runtime/` 和 `logs/`。
- 重复启动只打开浏览器，不重复启动服务。
- 停止快捷方式依次停止 FastAPI、静态服务器和 PostgreSQL。
- 失败时保留日志并显示最小错误提示。

## 7. 安装器

Inno Setup：

- `PrivilegesRequired=lowest`
- 默认目录：`{localappdata}\Programs\GaoerEnglishPractice`
- 创建桌面和开始菜单快捷方式。
- 安装完成可直接启动。
- 卸载前调用停止脚本；默认保留用户数据目录。

## 8. 验收

本机验收：

- 从空数据目录启动，自动建库、迁移、导入 500 题。
- 浏览器可完成练习、交卷、报告和原题回顾。
- 重复启动不产生第二组服务。
- 停止后重启，历史数据仍在。
- 构建脚本和旧系统门禁继续通过。

第二台电脑验收：

- 安装无需 Node/Python/Postgres/Docker。
- 无需管理员权限。
- 固定端口无冲突时可正常使用。
- 卸载后程序移除，用户数据按策略保留。

## 9. 已知风险

- PostgreSQL 固定端口 15432 与其他软件冲突时启动失败。
- 无代码签名证书，Windows SmartScreen 可能提示未知发布者。
- 便携 Python 和 PostgreSQL 体积较大，安装包预计数百 MB。
- 若目标电脑缺少 VC++ 基础运行库，需要额外验证或随包补齐。
- DeepSeek/本地模型不是安装成功的前置条件；薄弱点分析必须允许规则降级。
