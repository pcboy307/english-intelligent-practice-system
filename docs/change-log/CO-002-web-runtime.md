# CO-002：学生端一期改为 Expo Web

- 日期：2026-11-07
- 决定人：用户
- 变更类型：需求变更
- 版本：V11.1 → V11.2

## 内容

1. 保留 React Native + Expo 技术栈，一期使用 Expo Web（`react-native-web`）在电脑浏览器运行。
2. 手机真机验收推迟，不作为当前门禁。
3. 后端仍绑定 `0.0.0.0`；CORS 只允许 `http://localhost:8081` 与 `http://127.0.0.1:8081`。
4. Web 强制浅色，页面最大宽度 480 并水平居中。
5. Web 身份暂存 `localStorage`；安全等级低于原生安全存储，回到手机端时必须恢复 secure store。
6. 前端启动命令统一为 `npx expo start --web`，端口固定 8081；后端端口固定 8000。

## 未放松的约束

- Bank 隔离、双通道加权、两次跨会话消标、服务端 deadline、交卷前不下发答案。
- `design-tokens.json` 仍是视觉唯一来源。
- Web 代码同样禁止硬编码颜色、字号和间距。

## 待补齐

- 手机真机联通验收：未验收，待手机端阶段。
- secure store 恢复：待回补。
