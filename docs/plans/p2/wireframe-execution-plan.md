# P2 Host Wireframe 阶段执行计划

## 权威与范围

- 开发起点：`main@66253f8`。
- [总体架构](../../architecture/v2.0/overall-architecture-and-development-plan.md)、[测试计划](../../testing/v1.0/test-and-acceptance-plan.md)、[Artifact 权威契约](../../contracts/v1.0/artifact-state-authority-contract.md)、[Agent 契约](../../specifications/v1.2/agent-handoff-contract.md)和 [ADR-011](../../../DECISIONS.md)是本阶段权威。
- Wireframe 由 Host 规划；不新增 Wireframe Planner，不调用 Layout Planner、Visual Reviewer 或图片生成。
- P2 只负责页面分区、层级、关系和空间组织，不负责最终排版、视觉风格、PPT 构建或 Deck Assembly。

```text
P1 Authority Bundle
→ Host Wireframe Planning
→ Candidate Wireframe Specs
→ Deterministic Validation
→ Bounded Contract Correction
→ Accepted Wireframe Specs
→ Deterministic SVG Render
→ Optional Preview / Feedback
→ P2 Complete
```

## 调用预算与修正边界

逻辑 Pass 和真实 Host Model Invocation 分开计数。每个 Initial 或 User Revision Pass 最多包含一次 Planning Invocation 和两次 Contract Correction Invocation。M5 的 Initial + Revision 总预算为六次真实 Host 调用。

Validator 将问题分为 `correctable_contract_error`、`blocking_authority_error`、`redesign_required` 和 `preview_warning`。Correction 只能修改 Validator 明确指出的局部几何、引用、父子关系、连接、重叠和 Z-Order；每个操作必须绑定 Validation Issue。Correction 不得修改 Approved Content、Authority Hash、Layout Pattern 或完整 Region Graph，也不得用合法 Semantic/Focal 引用替换另一个合法引用。

## 契约与状态

P2 使用独立的 Layout Requirements、Per-Slide Spec、Deck Manifest、Validation Report、Correction Record、Preview、Feedback 和 State 契约。Layout Requirements 只允许密度、区域结构、视觉占位、布局方向、保留区和跨页结构一致性；颜色、字体、阴影、纹理和视觉氛围留给 P3。

状态闭环：

```text
received → validating_inputs
→ inputs_validated → wireframe_planning
→ candidate_specs_ready → validating_specs
├─ correctable → contract_correction_required → applying_contract_correction → validating_specs
├─ blocking / budget exhausted → wireframe_failed
└─ valid → specs_accepted → rendering → rendered → preview_recorded
   ├─ no pause → p2_complete
   └─ pause → awaiting_wireframe_feedback
      ├─ accepted / continue → p2_complete
      └─ changes_requested → revision_requested → wireframe_planning
```

Image-to-Editable-PPT 直接 `p2_bypassed`。

## 页面模型

- 坐标使用整数 `normalized_10000`；禁止 P2 Authority Artifact 使用浮点数。
- Page Spec 不包含 Deck Order；Order 只存在于 Manifest。
- `content_refs` 表示正式文字放置且必须 exactly once。
- `semantic_source_refs` 表示视觉区的内容来源，可重复引用，但必须来自当前页 Approved Content。
- Region 使用 `parent_region_id` 表达真正的层级；Parent-Child containment、同一 Overlap Group 和显式 Overlay 合法。
- Decoration 只有在低于内容 Z-Index 时可默认相交；前景 Decoration 必须显式 Overlay。

页面身份由 Slide ID、内容 Payload、页面规划元数据、结构化 Layout Constraints 和 Output Ratio 构成，不包含 Deck Order 或 P3-only 风格。仅 Order 变化时只更新 Manifest；单页输入变化只失效该页；Ratio 变化失效全部页面。

## SVG Renderer

SVG Renderer 从 Approved Slide Content 解析文字，Spec 不复制文字。短文本完整显示；长文本使用确定性前缀和省略号，并通过 `data-content-ref`、`data-authority-sha256`、`data-preview-display` 和 `data-authority-length` 保持追踪。预览截断是 Warning，不是内容丢失。

坐标投影采用有理数/Decimal 运算，`ROUND_HALF_EVEN`，最多三位小数，去除末尾零，禁止科学计数法和负零。相同输入必须得到逐字节一致 SVG。SVG 禁止 Script、`foreignObject`、事件处理器、外部链接、嵌入资源、本机路径和时间戳。

P2 只交付 SVG，不新增 PNG、Cairo、Chromium 或 PowerPoint 依赖。

## Gate

D03 是唯一 Live Host Smoke，必须覆盖 Content、Container + Child、Semantic Source、Relationship 和 Overlap/Overlay；执行一次 Initial Pass 和一次用户 Revision Pass，真实 Host 调用最多六次。D05、D08 使用确定性 Fixture，覆盖 internal-only、复杂容器、Chart Semantic Source、Order-only Manifest 更新和页面复用隔离。另使用一个 4:3 Fixture 验证投影。

P2 Gate 要求：Blocking Issues、Authority Drift、Invalid References、Unbounded Corrections、Automatic Redesign、Non-Deterministic/Unsafe SVG、Unexpected Page Rebuild 和 P0/P0.5/P1 Regression 全部为零。P2 通过前不得进入 P3，不创建 Release 或 Tag。
