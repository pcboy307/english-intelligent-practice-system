# Windows 自包含安装器验收记录

日期：2026-11-13

平台：Windows x64

需求版本：`V11.5`

## 构建结果

```text
File: dist/windows/GaoerEnglishPractice-Setup.exe
Size: 60.1 MB
SHA256: 2896403C66AF901EADC74A3C9787964B063E1AD09997BA6C0B791CEBD610E9AA
```

构建工具：

- Node.js 24
- Expo Web export
- Python 3.12 portable runtime
- PostgreSQL 16 portable binaries
- Inno Setup 6.7.3

## 本机安装

静默安装返回码：`0`

默认安装目录存在：

```text
%LOCALAPPDATA%\Programs\GaoerEnglishPractice
```

安装为每用户安装，未触发 UAC。

## 首次初始化

使用安装包内置 Python 和 PostgreSQL 执行：

```text
initdb -> 7 个迁移 -> 导入 seed
```

结果：

- Active Bank：`20261109_500`
- 72 篇
- 500 题
- 完形 12 篇 / 180 题
- 语法填空 12 篇 / 120 题
- 阅读 40 篇 / 160 题
- 七选五 8 篇 / 40 题

## 服务和浏览器

```text
API health: ok
API port: 8000
Web port: 8081
PostgreSQL port: 15432
GET /: 200
GET /practice (SPA fallback): 200
```

浏览器实测：

- 首页显示 `20261109_500`
- 成功开始一套 29 题练习
- 选择答案后自动进入下一题
- 交卷后自动进入报告页
- 报告正常显示

## 重复启动

重复执行桌面启动器前后端口 PID 保持一致：

```text
8000: 47648 -> 47648
8081: 32168 -> 32168
15432: 18000 -> 18000
```

没有生成第二组服务。

## 重启持久化

停止服务前：

```text
practice_sessions=2
practice_reports=2
active bank=20261109_500
```

停止并重新启动后：

```text
practice_sessions=2
practice_reports=2
active bank=20261109_500
```

## 卸载与重装

静默卸载返回码：`0`

- 程序目录已移除。
- `%LOCALAPPDATA%\GaoerEnglishPractice\data` 保留。
- `pgdata/PG_VERSION` 保留。

重新安装返回码：`0`，历史数据仍为：

```text
practice_sessions=2
practice_reports=2
active bank=20261109_500
```

## 多 Agent 记录

本轮尝试 3 个并行子 Agent：运行时、构建脚本、风险审查。

实际结果：

- 成功接收完整任务的子 Agent：`0/3`
- 3 个 Agent 均只返回“请说明任务”
- 判定：任务正文未进入有效子上下文，属于已知多 Agent 上下文丢失问题
- 处理：登记后改为主 Agent 串行执行，不宣称并行完成

## 未验证项

- 尚未在第二台物理电脑上执行安装，只在本机完成真实安装/卸载。
- 未进行商业代码签名，Windows SmartScreen 可能提示未知发布者。
- 未在含中文字符的程序安装路径下完成 PostgreSQL bootstrap；当前已验证默认 ASCII 用户路径。
- 未验证目标电脑已有软件占用 8000/8081/15432 时的用户提示体验。
- DeepSeek 或本地 Qwen 的可用性不属于安装门禁；不可用时报告自动使用规则降级。
