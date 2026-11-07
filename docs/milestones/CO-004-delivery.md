# CO-004 练习体验与解析修订交付

状态：实现完成，等待所有者验收。

## 版本

- `contracts/VERSION` 为 `V11.3`。
- `curriculum.json.requirement_version` 为 `V11.3`。
- 前端类型由 `contracts/openapi.yaml` 通过 `npm run generate:api` 重新生成。

## 语法填空

- 原语法语篇保留，空位改为 ①–⑩。
- 每题在语篇后提供 A/B/C/D 四个选项，选项来自同一动词形式或同一语法功能类别。
- 页面没有 `<input>` 或 `<textarea>`。
- `grammar_fill` 题型 ID、`grammar_tags` 和 Coverage 要求未改变。

## 按篇呈现

组卷输出顺序由后端固定为：

```text
CLOZE 15 题（ordinal 0–14）
GRAMMAR 10 题（ordinal 15–24）
GAP 5 题（ordinal 25–29）
```

前端一次展示一篇，顶部显示“第 x 篇 / 共 y 篇”，不强制答完才能进入下一篇。

## 报告与回顾

- 报告页有完整分数口径、三组题型正确率、Top3 薄弱点和 30 条中文解析。
- 最新报告检查：`30` 条解析全部含中文，英文整段数为 `0`。
- 每题提供“查看原题”；点击后进入 `/practice?session_id=X&review=1&q=N`。
- 回顾页只显示原题、我的选择、正确/错误，不包含解析。
- 交卷前“查看报告”按钮 disabled；交卷后原地进入只读回顾并启用按钮。

## 桌面布局

1920px 浏览器实测：

```text
内容容器：960px
正文栏：760px
选项高度：40px
选项字号：15px
选项行高：22.5px
选项间距：8px
按钮高度：40px
正文：16px / 1.75
```

700px 浏览器实测：内容容器 `480px`，符合 `<768px` 回落规则。

## 截图

- `qa/evidence/co004-desktop-practice.png`
- `qa/evidence/co004-desktop-report.png`
- `qa/evidence/co004-grammar-choice.png`

## 自动验证

```text
scripts/check-co004.py: PASS
6 passed
TypeScript: PASS
Expo dependencies: up to date
openapi.yaml: valid
M0_CHECK=PASS
API_CONTRACT_CHECK=PASS calls=7
```
