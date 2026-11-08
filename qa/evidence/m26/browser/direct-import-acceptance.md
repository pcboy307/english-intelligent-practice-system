# 直接导入题库验收

日期：2026-11-09

## 行为

- 选择题库 JSON 后立即调用 `POST /api/v1/banks/import`。
- 不调用 import preview。
- 不调用 DeepSeek 或任何质量校验。
- 仅保留题库名称非空、名称唯一及数据库写入所需的最小结构检查。
- 成功后立即切换为 active，并显示实际题库名称、篇数和题数。

## 浏览器实测

空名称文件：

- 提示：`题库名称不能为空`
- 未写库

重名文件：

- 文件名：`M2 Bank #2`
- 提示：`题库名称已存在，请换一个名称`
- 未写库

低质量文件：

- 名称：`Direct Import No Validation 20261109`
- 第 1 题解析为空
- 网络请求只有 `POST /banks/import?semantic_check=false`
- 返回 `201 Created`
- 首页立即显示该题库及 `1 篇 / 4 题`
- 页面提示：`已按原始内容直接落盘`

验收结束后测试题库已删除，当前题库恢复为 `20261108_500`。

## 验证

- 导入专项：`17 passed`
- 全量 pytest：`170 passed, 1 warning`
- `M0_CHECK=PASS`
- `API_CONTRACT_CHECK=PASS calls=25`
- OpenAPI 校验通过
- TypeScript `tsc --noEmit` 通过
- `migrations/006_unique_bank_name.sql` 已应用，数据库存在
  `question_banks_name_ci_unique` 唯一索引
