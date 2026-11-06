# 错误码契约

所有错误响应使用：

```json
{
  "error": {
    "code": "BANK_NOT_FOUND",
    "message": "可读说明",
    "request_id": "uuid",
    "details": {}
  }
}
```

| HTTP | code | 含义 |
|---:|---|---|
| 400 | `INVALID_REQUEST` | 请求结构或参数非法 |
| 400 | `INVALID_DURATION` | 练习时长不在配置中 |
| 400 | `ANSWER_FORMAT_INVALID` | 答案不符合题型要求 |
| 401 | `STUDENT_ID_REQUIRED` | 缺少或非法 `X-Student-Id` |
| 401 | `ADMIN_AUTH_FAILED` | 缺少或错误 `X-Admin-Token` |
| 403 | `ADMIN_LOCAL_ONLY` | `/admin/*` 请求来源不是回环地址 |
| 403 | `OWNER_APPROVAL_REQUIRED` | 服务端不存在该 Bank 的有效所有者审批记录 |
| 404 | `BANK_NOT_FOUND` | Bank 不存在 |
| 404 | `SESSION_NOT_FOUND` | 会话不存在或不属于该学生 |
| 404 | `QUESTION_NOT_FOUND` | 题目不存在或不属于当前 Bank |
| 409 | `BANK_NOT_ACTIVE` | 新会话没有 active Bank |
| 409 | `BANK_NOT_READY` | Bank 状态不允许激活 |
| 409 | `BANK_GENERATION_RUNNING` | Bank 已有运行中的生成 job |
| 409 | `BANK_APPEND_FORBIDDEN` | 试图向已有 Bank 追加题目 |
| 409 | `SESSION_SUBMITTED` | 会话已交卷，不能继续暂存答案 |
| 409 | `SESSION_BANK_IMMUTABLE` | 试图修改会话绑定的 Bank |
| 410 | `SESSION_EXPIRED` | 已超过服务端 deadline 且自动交卷完成 |
| 413 | `PAYLOAD_TOO_LARGE` | 请求体超过限制 |
| 422 | `SCHEMA_VALIDATION_FAILED` | Schema 校验失败 |
| 429 | `GENERATION_RATE_LIMITED` | 生成适配器触发限流 |
| 500 | `INTERNAL_ERROR` | 未预期服务端错误 |
| 502 | `LLM_ADAPTER_ERROR` | LLM 适配器调用失败 |
| 503 | `BANK_GENERATION_PAUSED` | 首批验收点等待人工继续 |
