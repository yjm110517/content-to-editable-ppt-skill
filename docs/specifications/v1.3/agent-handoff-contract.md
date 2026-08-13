# Content to Editable PPT Skill Agent 职责与交接契约 v1.3

## 文档地位

本文档是 [Agent 职责与交接契约 v1.2](../v1.2/agent-handoff-contract.md) 的增量权威版本，仅替换 P2 Wireframe 职责和 P2→P3 交接。Host、Layout Planner、Visual Reviewer 的其他边界继续有效。

## P2 负责人

Markdown Wireframe 由 Host Agent 完成。不得新增 Wireframe Planner Agent。

Host 负责：

- 读取已验证的 P1 Authority Bundle；
- 为每页生成干净的文字布局草稿；
- 表达页面分区、层级、相对位置、关系、阅读顺序和视觉预留区；
- 默认向用户展示整套线稿；
- 根据用户布局反馈创建新 Wireframe Revision；
- 将文字修改请求返回 P1。

Host 不得：

- 改写 Approved Slide Content；
- 自行拼写 Authority Metadata；
- 生成或调用 SVG Wireframe；
- 在 Contract Correction 中自动重新设计页面；
- 调用 Layout Planner、Visual Reviewer 或图片生成完成 P2。

## Deterministic Runtime 职责

未来 Markdown P2 Runtime 负责：

- 读取 P1 Authority 并注入完整页面内容；
- 写入唯一合法的 Slide/Content Ref 注释；
- 生成极薄 Manifest；
- 验证页数、顺序、Content Ref、内容漂移、Markdown 结构和 Hash；
- 原子保存 Revision 和状态；
- 生成隐藏内部 Metadata 的聊天展示版本。

在上述能力实现并通过新 Gate 前，Host 必须停止在 `P2 Markdown realignment pending`。

## P2→P3 交接

交接包包含：

- Approved Slide Content；
- Accepted `deck-wireframe.md`；
- `wireframe-manifest.json`；
- 用户视觉要求。

Layout Planner 不参与该交接。P3 Host 可以读取布局说明，但不得把布局说明当作正式页面文字。
