# Content to Editable PPT Skill Artifact、State 与权威数据契约 v1.3

## 文档地位

本文档是 [v1.2](../v1.2/artifact-state-authority-contract.md) 的增量权威版本。P1、P2.1、Resolution Record 和 Asset Manifest 的既有不可变规则继续有效。

## Authority

| Artifact | Authority | Mutability |
|---|---|---|
| P1 Approved Slide Content | 正式页面文字 | Immutable revision |
| P2 Markdown Wireframe | 内容组织和粗布局 | Immutable revision |
| P2.1 Accepted Manifest | Visual Placeholder 语义和 P1 来源 | Immutable revision |
| P3.1 Resolution Record | 准确匹配的标准资产 | Write once |
| P3.1 Asset Manifest | 物化和消费来源 Hash | Write once |
| Deck Visual System | 跨页视觉规则 | Immutable revision |
| Deck Prompt Package | 生图模板、负面约束和参数 | Immutable revision |
| Style Anchor Record | 用户确认的风格锚点 | Immutable revision |
| Design Preview Record | 用户确认的逐页视觉目标 | Immutable revision |
| Visual Reconstruction Spec | Preview 元素到 PPT 对象的映射 | Immutable iteration |
| Extracted Visual Asset Record | 从 Approved Preview 提取的独立位图 | Write once |
| Deck Consistency Report | 跨页视觉审核证据 | Append-only evidence |

## Prompt 与 Preview 绑定

每个 Design Preview Record 必须绑定：

```text
deck_visual_system_sha256
deck_prompt_package_sha256
style_anchor_sha256
approved_slide_content_sha256
wireframe_manifest_sha256
asset_manifest_sha256
slide_prompt_sha256
output_image_sha256
confirmed_user_message_sha256
```

任何输入变化都使旧确认失效。文字变化必须返回 P1；局部视觉变化只失效对应页面；Deck Visual System 或 Style Anchor 变化失效所有依赖页面。

## SVG 与提取 PNG

```text
Design Preview Source SVG Hash
= PPT Builder Input SVG Hash
= Asset Manifest sanitized_svg_sha256
```

无准确 SVG 时，Raster Handoff Pending 不能伪造 Resolution Success。提取完成后，Extracted Visual Asset Record 必须绑定 Approved Preview Hash、Visual Ref、Crop BBox、PNG Hash、背景处理状态和质量结果。

## 重建与交付

Visual Reconstruction Spec 必须绑定当前 Approved Preview Hash，且每个元素只能引用已批准 Content Ref、Visual Ref、Style Ref 和 Asset Ref。Final PPT 不是新的文字、结构、资产或视觉 Authority；其 Render 只能作为对比和交付证据。
