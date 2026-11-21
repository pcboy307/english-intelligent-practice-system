# 云电脑部署指南

## 推荐方式：安装器

适合 Windows 10/11 x64 云电脑，不需要管理员权限，也不需要安装 Node、Python、Docker、PostgreSQL。

1. 从 GitHub Releases 下载：

```text
GaoerEnglishPractice-Setup.exe
GaoerEnglishPractice-Setup.exe.sha256
```

2. 可先校验 SHA-256。
3. 双击安装。
4. 从桌面快捷方式启动。
5. 首次启动自动初始化数据库并导入 72 篇 / 500 题。

详细说明见 `docs/windows-installer-user-guide.md`。

## 源码部署

适用于需要修改代码或调试的 Windows 云电脑。

### 前置环境

- Git
- Node.js 24.x
- Python 3.12.x
- PostgreSQL 16.x

### 获取代码

```powershell
git clone <REPOSITORY_URL>
cd english-intelligent-practice-system
```

### 创建数据库

PostgreSQL 必须监听 `15432`，数据库名必须为 `english_practice`：

```powershell
C:\pgsql\bin\createdb.exe -h 127.0.0.1 -p 15432 -U postgres english_practice
```

如果数据库服务不是管理员安装版本，请根据云电脑实际 PostgreSQL 安装位置调整路径。

### 安装 Python 依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 执行迁移

在全新数据库上按文件名顺序执行：

```powershell
Get-ChildItem .\db\migrations\*.sql | Sort-Object Name | ForEach-Object {
  & 'C:\pgsql\bin\psql.exe' -h 127.0.0.1 -p 15432 -U postgres -d english_practice -v ON_ERROR_STOP=1 -f $_.FullName
}
```

### 导入 500 题 seed

```powershell
$env:DATABASE_URL='postgresql://postgres@127.0.0.1:15432/english_practice'
@'
import json
import psycopg
from backend.app.bank_transfer import import_bank

with psycopg.connect('postgresql://postgres@127.0.0.1:15432/english_practice') as connection:
    package = json.load(open('deploy/seed/20261109_500.json', encoding='utf-8'))
    print(import_bank(connection, package, strict_validation=False))
    connection.commit()
'@ | .\.venv\Scripts\python.exe -
```

### 环境变量

```powershell
Copy-Item .env.example .env
```

`.env` 中至少需要：

```text
ADMIN_TOKEN=<随机生成的本地管理口令>
DATABASE_URL=postgresql://postgres@127.0.0.1:15432/english_practice
WEAKNESS_ANALYSIS_DISABLED=0
```

如需 DeepSeek 薄弱点分析，再填写：

```text
DEEPSEEK_API_KEY=<你的密钥>
```

不要把 `.env` 提交到 GitHub。

### 安装前端依赖并启动

后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

前端：

```powershell
cd apps\mobile
npm ci
npx expo start --web --port 8081
```

访问：

```text
http://localhost:8081/
```

## Docker

当前仓库未提供生产级 Docker Compose。Windows 云电脑优先使用安装器；Linux 云主机若需要 Docker，请先完成 PostgreSQL 固定端口、迁移、seed 导入和 Expo Web 静态托管验证，再用于生产。

## 数据与安全

- 不要上传 `%LOCALAPPDATA%\GaoerEnglishPractice\data`。
- 不要上传 `.env`、数据库目录或日志。
- 不要把 DeepSeek API Key 写进代码、题库 JSON 或 README。
- `/admin/*` 仍只接受回环来源。
- 如果要把服务公开到互联网，必须增加 HTTPS、反向代理、身份认证和网络访问控制。

## 验证

```powershell
.\scripts\check-m0.ps1
.\scripts\check-api-contract.ps1
.\.venv\Scripts\python.exe -m pytest tests\desktop\test_desktop_runtime.py -q
```

再实际完成一次：启动练习、答题、交卷、查看报告、重启后查看历史报告。
