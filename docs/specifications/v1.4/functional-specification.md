# Content to Editable PPT Skill 功能规格说明 v1.4

## 文档地位

本文档增量替换 [v1.3](../v1.3/functional-specification.md) 的 P2→P3 交接。

## F04.1 Visual Placeholder Intent

P2 Candidate 每页必须声明稳定 `visual_ref`、受控 `role/subtype`、简短 `semantic`、当前页 `semantic_source_refs`，并在布局草稿中使用一次对应占位符。P2 不得决定图库、具体图标、路径、SVG、Hash 或最终视觉属性。

允许角色为 `icon`、`image`、`chart`、`diagram` 和 `illustration`。仅 `diagram` 允许 `process`、`timeline`、`cycle`、`relationship` 或 `architecture` subtype。Decoration 属于 P3。

## F05.1 Tabler-first Asset Resolution

P3.1 只接受 Accepted P2 1.1 Manifest 和 Deck Visual Direction 作为业务输入。标准图标优先从固定 Tabler Outline 库解析；唯一 canonical name 或 official alias 才可自动采用，其他候选由当前 P3 Host Pass 从 Top-K 选择。

Resolution Record 一经创建不可修改。Normalize、Sanitize 和物化 Hash 写入 Asset Manifest。复杂度依次按 Existing、最多两图标组合、受限 Primitive SVG、Raster/Image Handoff 路由。

P3.1 只证明同一 Sanitized SVG 能被 Preview Compositor 和 PPT Runtime 消费，不生成正式 Design Preview。

两条消费链必须记录同一个 `sanitized_svg_sha256` 作为输入来源。resvg 产生的 PNG 和 Pillow 合成结果分别记录自己的派生 Hash；PPT Builder 在调用前记录输入 SVG Hash。不得比较 SVG 与 PNG Hash，也不得要求 Office 保存后的 OOXML 媒体字节与输入 SVG 完全一致。

已解析 SVG 必须在后续 Preview Composition 和 PPT Runtime 中被物理消费，生成模型不得重绘、模拟或替换该图标。
