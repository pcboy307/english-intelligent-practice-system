# 后台本机鉴权契约

状态：M0 冻结候选。

## 1. 网络绑定

- 后端绑定 `0.0.0.0`，学生端必须能通过局域网访问。
- 不能为了后台安全把整个服务只绑定到 `127.0.0.1`。

## 2. `/admin/*` 双层门禁

请求必须依次通过：

1. 回环来源检查：socket 对端地址必须为 `127.0.0.1` 或 `::1`。
2. `X-Admin-Token` 检查：使用 `secrets.compare_digest` 与 `.env` 的 `ADMIN_TOKEN` 比较。

非回环来源直接返回 `403 ADMIN_LOCAL_ONLY`，不得进入 token 校验。

禁止依据 `X-Forwarded-For`、`Forwarded` 或任何客户端可伪造头判断来源。只使用 ASGI/Starlette socket 连接对象中的对端地址。

## 3. Token 生命周期

- 启动时读取 `.env` 的 `ADMIN_TOKEN`。
- 若缺失，生成高熵随机 token，写回 `.env`，仅在控制台打印一次。
- `.env` 已被 `.gitignore` 忽略。
- token 不得写入日志正文；审计日志仅保存 SHA-256 摘要前 8 个十六进制字符。

## 4. 所有者审批

- 客户端不再提交 `approved_by_owner` 布尔值。
- `/admin/banks/{bank_id}/approve-generation` 创建服务端持久化审批记录。
- `/admin/banks/{bank_id}/generate` 只接受数据库中尚未使用、未过期且绑定同一 Bank 的审批记录。
- 全量生成仍需系统所有者在对话中逐个批准，API 审批只是落库证据。

## 5. 审计

所有 `/admin/*` 写操作追加 `admin_audit_log`：

- UTC 时间；
- HTTP method；
- path；
- token SHA-256 指纹前 8 位；
- 操作结果；
- bank_id（如存在）。

## 6. M2 管理页面

- 首次打开要求输入管理口令。
- 口令只存浏览器内存，不写 localStorage、sessionStorage、IndexedDB 或 Cookie。
- 刷新页面后必须重新输入。
