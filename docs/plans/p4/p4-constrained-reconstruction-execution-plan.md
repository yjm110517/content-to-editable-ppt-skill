# P4 Constrained Reconstruction 执行计划

## 状态

```text
P3.3 Approved Design Preview   COMPLETE
P4 Constrained Reconstruction COMPLETE
P5 Deck Delivery              READY
```

P4 以 P3.3 已批准视觉证据、Reconstruction Seed、Element Map、P1 正式内容和批准资产为唯一输入，确定性生成真正可编辑、但仍禁止交付的多页候选 PowerPoint。

## 冻结流程

```text
Approved Design Preview + Reconstruction Seed
→ Deterministic Visual Reconstruction Spec
→ Reconstruction-class Smoke Set（1–2页）
→ Shared PowerPoint Page Build / Render
→ Structural / Editability / Fidelity QA
→ Issue-bound Targeted Patch（最多2次）
→ Multi-page Candidate Deck
→ PowerPoint Render All Slides
→ Post-Assembly Pixel Drift = 0
→ P4 Complete
```

完整 Seed 页面不执行 Initial Planner。Seed 不完整、需要改变 Reconstruction Class/P4 Strategy、替换资产或修改内容时必须返回 P3.3/P1，禁止通过看图猜测补齐。

P3.3 Preview 与 P4 Page/Deck 使用 `scripts/shared/ppt/` 下的同一组 Text、Shape、Line、Image、Chart、Asset 和 Text Layout Builder。Raw Generated Layer 默认不进入候选 Deck；批准的复杂视觉仅以独立 Raster 对象进入。

页面缓存按 Approved Preview、Element Map、Seed、Content、Asset、Chart、Visual System 和 Builder 版本建立。只有声明 `order_sensitive=true` 的页面把页码、章节序号、进度或导航绑定加入身份。

## Gate

[P4 Gate 报告](../../../reports/p4/p4-constrained-reconstruction-gate.json) 冻结以下证据：

- D03 三页真实 Approved Design Preview 完成重建；
- Initial Planner、Reviewer、Image Generation 调用均为 0；
- 三页 Seed Completeness 与 Native-required Editability 均为 100%；
- Raw Generated Layer 与 Full-slide Raster Substitution 均为 0；
- 单页重建后再组装三页 Candidate Deck；
- Candidate Deck 的 PowerPoint 逐页 Render 与最后通过的单页 Render 完全一致；
- D05 覆盖 Native Chart、Sanitized SVG 和 Card；
- D08 覆盖 Connector、Order-sensitive Cache 与恢复上限；
- P0 Baseline 与 P0–P3.3 回归保持不变。

P4 产物 `reconstruction-candidate.pptx` 始终包含 `delivery_forbidden=true` 的 Gate 证据。只有 P5 可以执行最终 Deck Consistency Review、Packaging 和 Delivery。
