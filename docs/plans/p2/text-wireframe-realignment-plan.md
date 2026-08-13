# P2 Markdown 文字线稿重对齐计划

## 当前决策

[ADR-035](../../../DECISIONS.md) 已将正式 P2 从 SVG Wireframe 重定义为 Host 生成的 Markdown 文字线稿。旧 [SVG P2 执行计划](wireframe-execution-plan.md)、PR #12–#16 和 Gate 报告保留为历史证据。

本文件定义文档重对齐后的下一实施阶段，不表示以下能力已经完成。

## 目标产物

```text
wireframes/
├─ deck-wireframe.md
└─ wireframe-manifest.json
```

Markdown 是唯一正式线稿内容本体；Manifest 只记录 Deck、P1 Authority、页序、Content Refs、Revision、Markdown Hash 和状态。

## 实施阶段

### M1 — Contract 与 Binder

- 定义极薄 Manifest Schema；
- 定义 Markdown 固定章节和 Metadata Grammar；
- 实现 Deterministic Binder，从 P1 Authority 注入完整页面内容；
- Host 只提供干净的布局草稿，不直接写内部 Metadata。

### M2 — Validator 与 State

- 验证 P1 Authority、页数、页序、Slide ID、Content Ref 和 Canonical Text；
- 验证每页页面内容、布局线稿和布局说明；
- 实现 Candidate、Accepted、Superseded 和 `p1_revision_required`；
- 原子保存 Revision，拒绝静默覆盖。

### M3 — Preview 与 Feedback

- 生成隐藏 Metadata 的聊天展示版本；
- 默认展示全部页面；
- 跳过查看只取消暂停；
- 布局修改创建新 Revision，文字修改返回 P1。

### M4 — Legacy Isolation

- 从 Production P2 Route 移除旧 Spec、Geometry Validator 和 SVG Renderer；
- 保留 Single-Slide Runtime 的 Sanitized SVG Asset 支持；
- 决定旧 P2 Python、Schema 和测试的归档或删除策略。

### M5 — Markdown P2 Gate

- 使用 D03、D05、D08 验证 Authority、完整性、内容、结构、Revision 和聊天展示；
- 断言 Production P2 的 SVG/PNG/Legacy Route 调用均为 0；
- 运行 P0、P0.5 和 P1 回归；
- Gate 通过后再更新 `SKILL.md` 为可执行 Markdown P2，并标记 P3 Ready。

## 当前停止规则

在 M1–M5 完成前：

```text
P1 complete
→ P2 Markdown realignment pending
→ STOP
```

不得调用旧 SVG P2，不得进入 P3，不得宣称完整 Content-to-PPT 可用。
