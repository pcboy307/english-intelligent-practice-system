# CO-006 交付说明

状态：实现完成，等待所有者验收。

## 界面

- 交卷确认改为居中弹窗，不再出现在页面底部。
- 练习页右上角固定显示上一题、下一题、查看报告、交卷和退出。
- 退出弹窗明确提示：“退出后会删除本次题目和已答记录，不会保存报告。”

## 数据行为

- 退出调用 `DELETE /api/v1/practice/{session_id}`。
- 只允许删除 `in_progress` 会话。
- 在单一事务中删除该会话的作答、题目快照、成功记录和会话记录。
- 不生成 `practice_reports`。
- 前端清除该会话的本地草稿和幂等键后返回首页。

## 验证

- 浏览器退出确认框实测可见，确认后 URL 返回 `http://localhost:8081/`。
- 退出会话在 `practice_reports`、`saved_answers`、`session_items`、`practice_sessions` 中的记录数均为 0。
- 交卷确认框实测为居中弹窗。
- 后端测试 `8 passed`。

证据：

- `qa/evidence/co006-exit-dialog.png`
- `qa/evidence/co006-submit-dialog.png`
- `qa/evidence/co006-evidence.txt`
