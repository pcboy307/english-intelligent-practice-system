# 高二英语智能练习 Windows 安装说明

## 系统要求

- Windows 10 或 Windows 11，64 位。
- 普通用户账号即可，不需要管理员权限。
- 不需要安装 Node、Python、Docker、PostgreSQL 或 Redis。
- 安装包：`GaoerEnglishPractice-Setup.exe`

## 安装

1. 把 `GaoerEnglishPractice-Setup.exe` 复制到目标电脑。
2. 双击运行。
3. 如果 Windows 提示“未知发布者”，选择“更多信息”后确认运行。当前安装包没有商业代码签名证书。
4. 按安装向导完成安装。
5. 桌面会出现“高二英语智能练习”快捷方式。

默认安装到：

```text
%LOCALAPPDATA%\Programs\GaoerEnglishPractice
```

不需要 UAC 提权。

## 首次启动

双击桌面快捷方式。首次启动会自动：

1. 初始化本地 PostgreSQL。
2. 创建 `english_practice` 数据库。
3. 执行数据库迁移。
4. 导入内置的 72 篇 / 500 题题库。
5. 启动本地后端和网页。
6. 用默认浏览器打开：

```text
http://127.0.0.1:8081/
```

首次启动可能需要数十秒，请不要连续重复双击。后续启动会复用已有数据，速度更快。

## 用户数据

练习记录、报告、错题和题库数据保存在：

```text
%LOCALAPPDATA%\GaoerEnglishPractice\data
```

卸载程序不会主动删除该目录。需要彻底清除数据时，可在确认不再需要历史记录后手动删除该目录。

## 固定端口

| 用途 | 端口 |
|---|---:|
| 浏览器页面 | 8081 |
| API | 8000 |
| PostgreSQL | 15432 |

如果其他程序占用这些端口，应用会启动失败。日志位于：

```text
%LOCALAPPDATA%\GaoerEnglishPractice\data\logs
```

## 停止服务

开始菜单中的“停止服务”会停止网页、API 和 PostgreSQL。

## 卸载

使用 Windows“设置 → 应用”或开始菜单中的卸载入口。卸载会移除程序文件，但保留用户数据目录。

## 当前限制

- 未使用商业代码签名证书，可能出现 SmartScreen 提示。
- 默认安装路径和数据路径应保持 ASCII。当前便携 PostgreSQL 在含中文的程序路径下执行 `initdb` 有兼容风险。
- 首次启动需要本机允许 PostgreSQL 在 15432 端口监听。
- 薄弱点分析在远程/本地模型不可用时会自动使用规则版分析，不影响练习和报告。
