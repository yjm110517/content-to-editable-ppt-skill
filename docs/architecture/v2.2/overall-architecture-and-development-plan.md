# Content to Editable PPT Skill 总体架构与开发计划 v2.2

## 文档地位

本文档是 [v2.1](../v2.1/overall-architecture-and-development-plan.md) 的增量权威版本。v2.1 已完成的 Markdown Wireframe Core 保持有效；本版新增 P2.1 Visual Placeholder Intent 与 P3.1 Tabler-first Asset Resolution，并同步当前阶段状态。

## 当前状态

```text
P0 / P0.5 / P1                COMPLETE
P2.0 Markdown Wireframe Core  COMPLETE
P2.1 Visual Placeholder       COMPLETE
P2 Overall                    COMPLETE
P3.1 Asset Resolution         COMPLETE
P3.2 Visual Design Brief      READY
P3.3 Design Image Generation  BLOCKED
```

## Authority 链

```text
P1 Approved Slide Content
→ P2.0 Markdown Layout Authority
→ P2.1 Visual Placeholder Intent
→ P3.0 Deck Visual Direction
→ P3.1 Immutable Resolution Record
→ Normalized / Sanitized Asset Manifest
→ P3.3 Preview Compositor + PPT Runtime
```

P2 只声明视觉语义、P1 内容来源绑定和布局位置。P3.1 决定具体资产。P3 Resolver 只从 Accepted P2 Manifest 读取 Placeholder；Markdown 仅作为 Manifest 绑定的 Authority Artifact 进行 Hash 和状态验证。

## P3.1 边界

P3.1 负责固定版本的本地检索、选择、组合、受限程序化回退、Normalize、Sanitize、Validate 和来源追踪。P3.1 不负责最终像素位置、颜色、Z-Order 或正式 Design Preview。

Design Preview 与 PPT Runtime 必须物理消费同一份 Sanitized SVG Source。比较的是两条链的 source-input Hash 与 Asset Manifest 的 `sanitized_svg_sha256`；不得要求 Rasterized PNG、Office 重写后的媒体字节与输入 SVG Hash 相等。P3.1 只运行 synthetic consumption fixture，正式 Preview 的位置、颜色、大小与 Z-Order 属于 P3.2/P3.3。

## 开发顺序

```text
P2.1 Contract + Gate
→ Tabler Vendor / Index / Search
→ Resolution / Materialization
→ Composition / Programmatic Fallback
→ P3.1 Gate
→ P3.2 / P3.3
```
