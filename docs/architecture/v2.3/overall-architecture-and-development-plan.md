# Content to Editable PPT Skill 总体架构与开发计划 v2.3

## 文档地位

本文档是 [v2.2](../v2.2/overall-architecture-and-development-plan.md) 的增量权威版本。v2.2 已完成的 P2.1 Visual Placeholder 与 P3.1 Tabler Core 保持有效；本版重新定义正式资产回退、Deck 视觉系统、设计图确认和受约束重建。

## 当前状态

```text
P0 / P0.5 / P1 / P2            COMPLETE
P3.1 Tabler Core                COMPLETE
P3.1 Production Fallback       COMPLETE
P3.2 Visual System / Prompt    COMPLETE (VISUAL QUALITY NOT EVALUATED)
P3.3 Design Preview            READY
P4 Reconstruction              BLOCKED BY P3.3 APPROVAL
P5 Deck Delivery               BLOCKED BY P4
```

历史 P3.1 Gate 证明 Existing、Composition、Programmatic 和 Raster Handoff 的工程能力，但新的正式生产链只接受准确匹配的 Tabler SVG，或在没有准确匹配时进入 `Raster Handoff Pending`。在生产路由和 Gate 完成隔离前，不得把 P3.1 Production Fallback 标记为完成。

## 最终产品链路

```text
P1 Approved Slide Content
→ P2 Markdown Wireframe
→ P2.1 Visual Placeholder Intent
→ P3.1 Resolved Standard Assets
→ P3.2 Deck Visual System + Locked Prompt Package
→ Approved Style Anchor
→ P3.3 Approved Design Previews
→ P4 Visual Reconstruction Specs
→ Editable Per-slide PPT
→ Deck Assembly + Final Render Comparison
```

项目先获得高质量、用户认可的图片版设计，再以文字、结构、资产和确认设计图为约束重建可编辑 PowerPoint。Design Preview 不是普通参考图，而是确认后的视觉权威；P1 仍是唯一正式文字权威。

## Authority 分层

| 阶段 | Authority |
|---|---|
| P1 | 标题、正文、数字、标签和数据 |
| P2 | 内容组织、粗粒度布局和阅读关系 |
| P2.1 | 视觉语义、P1 来源绑定和布局位置 |
| P3.1 | 已解析标准资产及来源 Hash |
| P3.2 | 跨页视觉系统和生图 Prompt Package |
| P3.3 | 用户确认的页面视觉目标 |
| P4 | Preview 元素到 PPT 对象的确定性映射 |
| P5 | 最终交付物和 Deck 级验证 |

P4 不重新猜文字、语义或资产，只恢复位置、比例、层级、构图和样式。

## P3.1 正式资产边界

```text
准确匹配的固定 Tabler SVG
→ Normalize → Sanitize → Validate

无准确匹配
→ Raster Handoff Pending
→ Approved Design Preview
→ 提取目标小型视觉元素
→ 独立 PNG
```

Two-icon Composition 和 Programmatic SVG 不再属于正式生产回退。它们的代码、测试和历史报告可以保留为工程证据，但 Skill 不得调用它们完成正式任务。

## P3.2/P3.3 设计边界

P3.2 冻结 Deck Visual System、Prompt Package、Negative Prompt、生成参数和 Style Anchor。每页 Prompt 由确定性程序注入内容、线稿、Visual Placeholder、Resolved Assets 和 Slide Role；Host 不得逐页重写整体视觉风格。

正式文字和已解析 SVG 必须由确定性 Compositor 注入 Design Preview。生成模型不得成为文字权威，也不得重绘或替换已解析标准图标。

所有 Deck 默认先确认 Style Anchor，再有限并行生成其余页面。页面修改按 Slide ID 局部失效；只有全局视觉系统或 Style Anchor 变化才允许扩大失效范围。

## 可编辑性与保真原则

- 标题、正文、数字和标签使用原生 PowerPoint 文本；
- 卡片、线条、箭头和基础流程使用原生 Shape；
- 表格与数据图表使用原生或可编辑结构；
- 准确匹配的标准图标使用 Sanitized SVG；
- 无匹配图标、复杂插画和场景使用独立 PNG/JPEG；
- 禁止把包含正式内容的整页位图作为最终页面背景。

视觉验收采用 `Perceptual Structural Fidelity over Pixel Fidelity`。整体构图、主元素比例、层级、留白、视觉焦点和显著重叠属于 Critical/Major；阴影、渐变、纹理和微小渲染差异属于 Minor。

## 时间与调用控制

```text
Deck Visual Direction Host Pass = 1
Prompt Compilation Agent Calls = 0
Style Anchor Generation = 1
Initial Design Generation <= 1 per slide
Automatic Design Regeneration = 0
Automatic Full-deck Redesign = 0
Technical Retry <= 2 per stage
Deck Consistency Review = 1
Per-page Reviewer = exception pages only
```

不设置固定总时长 SLA，但生图前必须完成全部确定性检查；任一 Blocking 立即停止后续模型调用。实现必须支持 Hash 缓存、断点恢复、页面级失效、3–4 页可配置批次、Contact Sheet 集中反馈，以及全量重建前的高风险页 Reconstruction Smoke。

## 后续开发顺序

```text
Production Fallback Cutover
→ P3.2 Deck Visual System + Prompt Compiler
→ P3.3 Style Anchor + Design Preview Approval
→ Preview Element Extraction
→ P4 Constrained Reconstruction
→ P5 Deck Assembly + Final Gate
```

详细实施边界见 [P3 视觉设计与受约束重建计划](../../plans/p3/visual-design-and-constrained-reconstruction-plan.md)。
