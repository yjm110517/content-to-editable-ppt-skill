# P2.1 Visual Placeholder 与 P3.1 Tabler Asset Resolution 执行计划

## 状态与已完成基线

本计划细化 [总体架构 v2.2](../../architecture/v2.2/overall-architecture-and-development-plan.md)、[功能规格 v1.4](../../specifications/v1.4/functional-specification.md)和[测试计划 v1.2](../../testing/v1.2/test-and-acceptance-plan.md)。

```text
P2.0 Markdown Wireframe Core       COMPLETE
P2.1 Visual Placeholder Intent     COMPLETE
P2 Overall                         COMPLETE
P3.1 Vendor / Index / Search       COMPLETE
P3.1 Materialization / Fallback    COMPLETE
P3.1 Final Gate                    COMPLETE
P3.2 Visual Design Brief           READY
P3.3 Design Image Generation       BLOCKED BY P3.2
```

已合并实现保留：

- PR #22：架构、规格、Authority、测试和 ADR 文档基线；
- PR #23：P2 Candidate/Manifest 1.1、Visual Placeholder、Binder、Validator 和 P2.1 Gate；
- PR #24：Tabler 下载、同步白名单、Vendor Lock、5,130 图标离线索引与保守检索。

后续不得回滚或重写这些历史。尚未提交的 Materialization 实现必须以本计划为准重新审核。

## 阶段边界与 Authority

```text
P1 Approved Slide Content
        ↓ Text Authority
P2.0 Markdown Wireframe
        ↓ Layout Authority
P2.1 Visual Placeholder Intent
        ├─ visual_ref
        ├─ role / subtype
        ├─ semantic
        ├─ semantic_source_refs
        └─ layout placement
        ↓
P3.0 Deck Visual Direction
        ↓
P3.1 Tabler-first Asset Resolution
        ↓
Immutable Resolution Record
        ↓
Normalize → Sanitize → Validate
        ↓
Asset Manifest + Consumption Contract
       ┌┴──────────────────────────┐
       ▼                           ▼
P3.3 Preview Compositor       PPT Runtime Builder
```

P2 只声明视觉语义、P1 内容来源绑定和布局位置。P2 不决定图库、图标名、版本、路径、SVG、颜色、线宽或装饰。

P3 Resolver 的业务输入只有 Accepted P2 1.1 Manifest 和 Deck Visual Direction。`deck-wireframe.md` 仅作为被 Manifest Hash 绑定的 Authority Artifact进行路径、Deck、Revision、状态和 Hash 检查；Resolver 不从 Markdown 重新解析 `visual_ref`、`role` 或 `semantic`。

P2 1.0 Artifact 保留为历史证据，但不得进入 P3。旧线稿必须从原 P1 Authority 创建新的 P2 Revision，不能自动猜测匿名视觉 Zone。

## Visual Placeholder

P2 1.1 Manifest 中的 Placeholder 结构为：

```json
{
  "visual_ref": "S03-V01",
  "role": "icon",
  "subtype": null,
  "semantic": "人工智能",
  "semantic_source_refs": ["S03-C02"]
}
```

允许角色：`icon`、`image`、`chart`、`diagram`、`illustration`。只有 `diagram` 允许 `process`、`timeline`、`cycle`、`relationship`、`architecture` subtype。Decoration 由 P3.2/P3.3 决定，不进入 P2 Authority。

每个 `visual_ref` 必须在 Deck 内唯一、绑定当前 Slide，并通过 `{{p2:visual-ref=S03-V01}}` 在布局草稿中恰好出现一次。`semantic_source_refs` 必须非空且只能引用当前页 Approved Content；它表达“视觉意图来自哪段内容”，不形成第二份文字 Authority。

## Vendor 与工具冻结

```text
Tabler Icons        v3.46.0
Pinned Commit       8ac7d81b72ece11072ef25ea9fd92e80c6f3c9fc
@resvg/resvg-js     2.6.2
Node                >=20，Gate 记录实际版本
Reference Platform  Windows x64
```

研究镜像使用默认 Cone Mode：

```powershell
git clone `
  --depth 1 `
  --filter=blob:none `
  --sparse `
  --branch v3.46.0 `
  https://github.com/tabler/tabler-icons.git `
  .vendor-sources/tabler-icons

git -C .vendor-sources/tabler-icons sparse-checkout set icons/outline
```

Sparse Checkout 只负责缩小研究工作树。正式 Vendor 白名单由同步脚本控制，且只复制：

```text
LICENSE
aliases.json
icons/outline/**
```

同步必须验证 Commit、Tag、Clean Worktree、无 Symlink/Reparse Point、图标数量和目录 Hash。研究镜像与 Managed Runtime 副本均 Git ignored；仓库只提交 Vendor Lock 和 License Attribution。

`@resvg/resvg-js` 必须固定在 Node lockfile、Vendor Lock 和 Runtime Manifest 1.1 的 `tools.svg_rasterizer`。Runtime Manifest 1.0 继续兼容 P0/P0.5；只有进入 P3.1 Consumption Gate 才要求 1.1。

## 检索、选择与 Resolution Record

自动采用只允许：

```text
唯一 Exact Canonical Icon Name
或
唯一 Exact Official Alias
```

其他结果必须稳定返回 Top-K，由当前 P3 Host Pass 选择，不新增 Host Pass、独立 Agent 或 Icon Reviewer。排序分数只用于 Evidence，不作为 v1 产品阈值。未来积累真实 Fixture 后，再依据 `precision@1` 和 `top-k recall` 决定是否扩大自动选择。

Resolution Record 创建后不可修改：

```json
{
  "visual_ref": "S03-V01",
  "p2_manifest_sha256": "...",
  "resolution_method": "tabler_existing",
  "library": "tabler-icons",
  "library_version": "3.46.0",
  "icon_name": "code-ai",
  "source_sha256": "...",
  "selection_method": "host_from_top_k"
}
```

Normalize 与 Sanitize 的派生 Hash 不得回写 Resolution Record，而应写入 Asset Manifest：

```json
{
  "resolution_record_sha256": "...",
  "source_svg_sha256": "...",
  "normalized_svg_sha256": "...",
  "sanitized_svg_sha256": "...",
  "sanitized_path": "assets/S03-V01.sanitized.svg"
}
```

## 同源资产 Hash 链

Design Preview 和 PPT Runtime 的一致性依据是两条链消费同一份 Sanitized SVG Source，不是 SVG 与派生 PNG/OOXML 的字节 Hash 相等。

```text
Asset Manifest.sanitized_svg_sha256
        │
        ├─ Composition Plan.sanitized_svg_sha256
        │      ↓ resvg-js
        │  rendered_icon_png_sha256
        │      ↓ Pillow Alpha Compose
        │  synthetic_preview_sha256
        │
        └─ PPT Builder source_input_sha256
               ↓ PowerPoint / OOXML
           relationship + media + render checks
```

必须满足：

```text
Design Preview Source Asset Hash
= PPT Runtime Source Asset Hash
= Asset Manifest Sanitized SVG Hash
```

不要求：

```text
Rendered PNG Hash = SVG Hash
PowerPoint OOXML Media Hash = Input SVG Hash
```

Office/COM 可能重新序列化媒体，因此 PPT Runtime 在调用 Builder 前记录并验证输入 SVG Hash；保存后只验证媒体存在、关系安全和渲染结果。

Resolved Icon 必须在后续 Design Preview Composition 和 PPT Runtime 中物理消费同一 SVG。生成模型不得重绘、替换或模拟已经解析的图标。

## P3.1 Consumption Contract

P3.1 输出极薄契约：

```json
{
  "visual_ref": "S03-V01",
  "resolution_record_sha256": "...",
  "asset_manifest_entry_sha256": "...",
  "sanitized_svg_sha256": "..."
}
```

它不包含像素位置、颜色、尺寸、Slot、Z-Order、Base Image 或正式 Design Preview 字段。

P3.1 只用 synthetic fixture 证明双端可消费：

```text
固定白底
+ 固定 Sanitized SVG
→ @resvg/resvg-js 2.6.2
→ transparent PNG
→ Pillow Alpha Compose
→ test-preview.png
```

Gate 分别记录 `sanitized_svg_sha256`、`rendered_icon_png_sha256`、`test_preview_sha256`、resvg 版本、Node 版本和平台。真实页面位置、色彩、大小与合成属于 P3.2/P3.3。

## 回退顺序

```text
Existing Tabler
→ 最多两个 Tabler 图标组合
→ 受限 Programmatic SVG
→ Raster/Image Handoff
```

Programmatic SVG 必须满足：

```text
viewBox = 0 0 24 24
primitive_count <= 12
group_depth <= 3
text = 0
external_assets = 0
freeform_bezier = false
raw_svg / raw_xml / arbitrary path = forbidden
```

组合与程序化回退仍须产生不可变 Resolution Record，并走同一 Normalize、Sanitize、Validate、Asset Manifest 和 Consumption Contract 链。

## 剩余 PR 顺序

已完成 PR #22–#24 保留。剩余工作严格顺序执行：

1. `codex/p3-icon-resolution-materialization`
   - Immutable Resolution Record；
   - Normalize、Sanitize、Asset Manifest 1.4；
   - Runtime Manifest 1.1；
   - Consumption Contract；
   - Builder source-input Hash 记录。
2. `codex/p3-icon-fallback`
   - Two-icon Composition；
   - Simple Drawing Schema；
   - Programmatic SVG；
   - Raster Handoff。
3. `codex/p3-icon-resolution-gate`
   - synthetic Preview consumption；
   - PPT Runtime source-input consumption；
   - D03/D05/D08 和全量回归。

每个 PR 执行：

```text
latest main
→ deterministic tests
→ review
→ merge
→ post-merge verify
→ next
```

任一 Blocking 立即停止。不重新运行 P2 Host，不增加独立 Agent，也不在 P3.1 生成正式 Design Preview。

## Final Gate

```text
Primary Library = Tabler only
Online Resolution Calls = 0
Hallucinated Icon Paths = 0
Arbitrary Host SVG = 0
Independent Icon Reviewer Calls = 0
Resolution Record Overwrites = 0
Composition Input Sanitized SVG Hash = Asset Manifest Sanitized SVG Hash
PPT Builder Source Input SVG Hash = Asset Manifest Sanitized SVG Hash
Rendered Icon PNG Hash = recorded resvg output
Synthetic Preview Hash = recorded Pillow composition output
Generative Icon Substitution = 0
P2 Authority Drift = 0
P0/P0.5/P1/P2 Regression = 0
```

P3.1 Gate 通过只代表资产解析完成。只有到 P3.3 时才生成正式 Design Preview。
