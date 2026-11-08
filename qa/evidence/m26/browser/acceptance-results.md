# 题库导入与删除验收记录

日期：2026-11-08
环境：`http://localhost:8081` / PostgreSQL `127.0.0.1:15432 / english_practice`

## 自动化

- 题库导入删除专项：`11 passed`
- 全量 pytest：`152 passed, 1 warning`
- `M0_CHECK=PASS`
- `API_CONTRACT_CHECK=PASS calls=24`
- OpenAPI 3.1：Swagger 校验通过
- TypeScript：`tsc --noEmit` 通过

## 浏览器实测

导入：

- 使用 `ui-import-test-package.json`，1 篇 / 4 题。
- 预览显示名称、篇数、题数、题型构成和 DeepSeek 审题选项。
- DeepSeek 独立审题 1 篇，实际成本 `¥0.0240`。
- 导入成功后首页立即显示 `UI Import Test 20261108 · 共 4 题`。
- 导入事务完成后，新库为 active，原 `M2 Bank #2` 转 archived。

删除：

- active 行显示不可删除按钮且禁用。
- 非 active 库删除预览显示篇数、题数、会话、报告、作答和错题实际条数。
- 弹窗包含“此操作不可恢复”。
- 确认按钮实测：
  - 初次出现：`disabled=true, text=请稍候…`
  - 1.5 秒后：`disabled=false, text=确认，此操作不可恢复`
- 确认后从列表和数据库永久移除。

回环限制：

- 非回环来源调用导入预览返回 `403 ADMIN_LOCAL_ONLY`。
- 非回环来源调用删除预览与删除接口均返回 `403 ADMIN_LOCAL_ONLY`。

## 清理状态

- `UI Import Test 20261108` 数据库残留行数：`0`
- 当前 active：`M2 Bank #2`
- 测试未留下 `Import test *` 题库。

## 截图

- `bank-switch-import-delete.png`
- `bank-import-preview.png`
- `bank-import-success.png`
- `bank-delete-confirm.png`
- `bank-delete-success.png`
