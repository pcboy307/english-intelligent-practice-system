# Windows 自包含安装器构建说明

## 目标

生成：

```text
dist/windows/GaoerEnglishPractice-Setup.exe
```

安装包面向 Windows 10/11 x64，按当前用户安装，不要求管理员权限。安装后不要求 Node、Python、Docker 或 PostgreSQL。

## 前置工具

- Node 24：`C:\Users\Administrator\node24`
- Python 3.12：项目 `.venv`
- PostgreSQL 16 二进制：`C:\pgsql`
- Inno Setup 6

安装 Inno Setup：

```powershell
winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
```

## 构建

```powershell
.\scripts\build-windows-installer.ps1
```

只准备运行目录、不生成安装器：

```powershell
.\scripts\build-windows-installer.ps1 -SkipInstaller
```

复用现有 Expo Export：

```powershell
.\scripts\build-windows-installer.ps1 -SkipFrontendBuild
```

## 暂存目录

```text
dist/windows/package/
  backend/
  config/
  contracts/
  db/
  desktop/
  seed/bank.json
  web/
  runtime/python/
  runtime/pgsql/
```

## 运行时数据

用户数据不放在安装目录：

```text
%LOCALAPPDATA%\GaoerEnglishPractice\data
```

其中包含 PostgreSQL data、日志和 PID 文件。安装升级不得删除该目录。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests\desktop\test_desktop_runtime.py -q
.\scripts\check-m0.ps1
.\scripts\check-api-contract.ps1
```

安装器需要在本机完成一次真实安装、启动、交卷、重启持久化和卸载验证。
