# 半日浏览器最小闭环交付

状态：目标 A 已跑通，等待所有者复核。

## 今日目标

浏览器完成一套 30 分钟练习并看到报告，数据持久化到 PostgreSQL。

## 今日不包含

- 60 分钟卷。
- 错题本页、趋势页、后台管理页。
- 手机真机。
- 全量 2000 题 Bank。
- 雷达图、动效、富文本解析。
- 完整生产测试套件与长文档。

## 运行环境

| 项 | 实测值 |
|---|---|
| Node.js | `v24.22.2`，官方 Windows ZIP，位于 `C:\Users\Administrator\node24` |
| Python | `3.12.10` |
| PostgreSQL | `16.15`，官方 Windows ZIP，位于 `C:\pgsql` |
| PostgreSQL 数据目录 | `C:\pgdata` |
| PostgreSQL 端口 | `15432` |
| 数据库 | `english_practice` |
| FastAPI | `0.0.0.0:8000` |
| Expo Web | `localhost:8081` |

## 浏览器闭环

运行命令：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

$env:PATH = 'C:\Users\Administrator\node24;' + $env:PATH
Set-Location apps\mobile
npx expo start --web --port 8081
```

实际路径：

```text
http://localhost:8081/ → 开始 30 分钟练习 → /practice → 交卷 → /report
```

报告显示：

- `46.67` 分。
- `grammar_fill 10%`、`cloze 80%`、`gap_fill 20%`。
- 三项薄弱知识点。
- 30 条逐题答案、正确答案与纯文本解析。

截图：

- `qa/evidence/m1/home.png`
- `qa/evidence/m1/practice.png`
- `qa/evidence/m1/report.png`

## 持久层证据

PostgreSQL 实测：

```text
current_database | version
english_practice | PostgreSQL 16.15, compiled by Visual C++ build 1944, 64-bit
```

接口测试在真实 PostgreSQL 上运行：

```text
4 passed, 1 warning in 11.60s
```

覆盖：30 题组卷、交卷前无答案、报告落库、交卷幂等、跨会话两次消标、CORS 与 `/admin` 回环守卫。

## 交卷前答案保密

实测创建会话响应保存于 `qa/evidence/m1/pre-submit-response.json`：

```json
{
  "question_count": 30,
  "has_answer": false,
  "has_explanation": false,
  "keys": "session_id,bank_id,bank_name,bank_version,duration_minutes,status,items,composition_note,deadline,server_time,remaining_seconds,progress"
}
```

## 幂等与两次消标

复现命令：

```powershell
.\.venv\Scripts\python.exe scripts\evidence_half_day.py
```

幂等摘要：

```json
{"first_score":100.0,"second_score":100.0,"responses_equal":true}
```

psql 原始结果：

```text
                  id                  |  status   |        submit_idempotency_key        | report_rows
--------------------------------------+-----------+--------------------------------------+-------------
 313e3d39-8539-4ce1-b415-196029d15bd0 | submitted | 7188e6a7-653f-4d75-adb8-55d257ef9187 |           1
(1 row)
```

两次不同会话答对后：

```text
              student_id              | question_id |  status  | streak | success_rows
--------------------------------------+-------------+----------+--------+--------------
 8e448699-c126-4b31-85d2-e1ef7fd00882 | DEMO-G01    | mastered |      2 |            2
(1 row)
```

同一会话重复使用相同幂等键不会增加 success 行，因此 streak 不会在同套内增长到 2。

## 数据库端口守卫

正常启动时 `inet_server_port()` 必须等于 `15432`。将期望端口人为改为 5432 后，启动原文：

```text
RuntimeError: DATABASE_PORT_MISMATCH: inet_server_port()=15432 expected=5432
```

## 前端调用与 OpenAPI 对照

复现命令：

```powershell
.\scripts\check-api-contract.ps1
```

结果：

```text
/bank/active                  /bank/active                   True
/practice/start               /practice/start                True
/practice/${sessionId}        /practice/{session_id}         True
/practice/${sessionId}/answer /practice/{session_id}/answer  True
/practice/${sessionId}/submit /practice/{session_id}/submit  True
/reports/${sessionId}         /reports/{session_id}          True
API_CONTRACT_CHECK=PASS calls=6
```

## 历史嵌入式 PostgreSQL 初始化报错

此前失败属于 locale/编码问题，原文结尾：

```text
performing post-bootstrap initialization ...
[STDERR] ... FATAL: invalid byte sequence for encoding "UTF8": 0xb2
child process exited with exit code 1
initdb: removing data directory ...
```

同时出现：

```text
initdb: could not find suitable text search configuration for locale "Chinese (Simplified)_China.936"
```

没有出现 administrative permissions、VCRUNTIME140.dll/MSVCP140.dll 缺失或下载失败。官方 ZIP 改用 ASCII 目录、`UTF8` 和 `--locale=C` 后成功。

## 视觉证据

强调色硬编码 grep：

```text
contracts/design-tokens.json:24:    "accent": "#2C5F5A",
```

代码只通过 `tokens.color.accent` 使用；强调色仅用于进度条与选中控制。主按钮仍为 `#111111` 底、`#FFFFFF` 字；圆角、字号和间距均从 tokens 读取。
