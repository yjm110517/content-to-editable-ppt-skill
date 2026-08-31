# Stage 3 Reconstruction Plan Contract

> **Status**：Working Guidance / Pre-ADR Contract  
> **Document type**：Stage 3 Canonical Artifact Contract  
> **Applies to**：Canonical Reconstruction Plan / Revision Patch / Stage 3 deterministic compiler  
> **Design baseline before contract drafting**：`8122f32 docs: refine visual-first agent architecture`
> **First repository commit containing this contract**：`03d66aa docs: add stage 3 prompt contracts`
> **Last updated**：2026-08-31  
> **Runtime authority**：非运行权威；不覆盖当前 `layout.json`、`crops.json`、`asset_manifest.json`、正式 Schema、Runtime 或 Accepted ADR。  
> **Decision dependency**：只有在 Stage 2 Benchmark 通过并进入后续 ADR / Implementation 后，才允许据此修改正式 Schema、Compiler 与 Runtime。

---

# 1. 文档目的

本文档冻结 Visual-first Stage 3 中**统一重建计划（Canonical Reconstruction Plan）**的语义合同。

它回答的不是：

> 最终 JSON 每个字段叫什么？

而是：

> **一份可被确定性程序执行、验证、修订、审计和重新构建的页面重建计划，必须表达哪些事实。**

本文档用于约束：

- Layout Planner Agent 的正式输出；
- Revision Patch；
- 确定性 Plan Compiler；
- 单页构建；
- 结构 / 可编辑性 QA；
- Visual Reviewer Context Compiler；
- Accepted Page Plan；
- Final Deck Shared Builder。

后续具体 JSON Schema、文件名、字段名、单位与实现代码必须遵守本合同。

---

# 2. 核心原则

Canonical Reconstruction Plan 是 Stage 3 的**唯一规范化页面重建计划**。

目标链路：

```text
Stage 1 Authority
+
Stage 2 Important Visual Objects
+
Approved Design
        ↓
Layout Planner
        ↓
Canonical Reconstruction Plan
        ↓
Deterministic Validation / Compilation
        ↓
Current Runtime Artifacts
        ↓
PPT Build
```

核心原则：

> **Agent 负责形成声明式重建计划；程序负责确定性验证、转换、构建和资产落地。**

---

# 3. Plan 不是什么

Canonical Reconstruction Plan 不是：

- 一份新的 Stage 1 内容源；
- 一份新的图表 / 表格数据源；
- 最终 PPTX；
- `layout.json` 的简单改名；
- `crops.json` 的简单合并；
- `asset_manifest.json` 的简单合并；
- PowerPoint OOXML；
- PptxGenJS 代码；
- COM 调用脚本；
- Visual Reviewer 报告；
- 图片生成 Prompt；
- Agent 的自然语言工作日志。

它是：

> **从上游权威信息到可编辑 PPT 构建之间的声明式中间表示。**

---

# 4. Plan 的权威边界

Canonical Reconstruction Plan 不能覆盖上游权威事实。

| 信息 | 权威来源 | Plan 的职责 |
|---|---|---|
| 正式文字 | Stage 1 Canonical Content | 引用，不重写 |
| 数字、单位、专名、结论 | Stage 1 Canonical Content | 引用，不重写 |
| Chart / Table 正式数据 | Stage 1 Structured Data | 引用，不猜测 |
| Stage 1 语义对象 | Stage 1 Semantic Structure | 引用对象身份 |
| Stage 1 流程 / 层级 / 阅读顺序 | Stage 1 Semantic Structure | 引用关系 |
| Stage 2 重要视觉对象 | Stage 2 Visual Object Record | 引用对象身份 |
| 最终构图与视觉效果 | Approved Design | 转化为近似几何与主要样式 |
| 重建方式 | Reconstruction Policy + Layout Planner | 记录决策 |
| 最终实际资产 | Deterministic Runtime | 运行后补充 / 绑定 |

因此：

> **Plan 是重建决策的权威，不是内容事实的权威。**

---

# 5. 页面级结构

一份 Canonical Reconstruction Plan 对应一页幻灯片。

概念上至少包含以下层次：

```text
Page Identity
│
├─ Elements
│
├─ Visual / Stage 3 Relations
│
├─ Asset Requests
│
├─ Revision State
└─ Provenance
```

具体字段名不在本合同冻结。

---

# 6. Page Identity

Plan 必须能唯一识别当前页面。

至少需要表达：

- page / slide identity；
- 所属 deck / run；
- plan version；
- 当前状态；
- 上游输入版本绑定。

概念示例：

```yaml
page:
  id: slide_03

plan:
  version: 2
  status: planned
```

具体命名由后续 Schema 决定。

---

# 7. Element 的定义

Element 是 Canonical Reconstruction Plan 中的最小独立重建单位。

v1 冻结原则：

> **只有需要独立构建、独立定位、独立编辑、独立裁切或独立控制层级的对象，才成为独立 Element。**

---

# 8. Element 粒度

## 8.1 应独立成为 Element 的对象

例如：

- 正式标题；
- 正式正文块；
- 独立标签；
- 可编辑卡片底板；
- 独立序号徽章；
- 重要图标；
- 原生 Chart；
- 原生 Table；
- Connector / Arrow；
- 复杂裁切插画；
- 独立照片；
- 需要单独控制 z-order 的重要视觉对象。

---

## 8.2 不应无意义拆分的内容

以下内容通常不应单独成为 Element：

- 阴影；
- 圆角；
- 填充颜色；
- 边框；
- 小范围 glow；
- 微小 decorative spark；
- subpixel visual effects。

这些应优先作为：

```text
style
```

或作为更高层视觉资产的一部分。

---

# 9. 复合对象

一个语义对象可以由多个可构建 Element 组成。

例如：

```text
step_1
├─ step_1_background
├─ step_1_badge
├─ step_1_number
└─ step_1_title
```

其中：

```text
step_1
```

可以作为语义组 / group identity，

而内部对象分别承担：

- native shape；
- native text；
- independent positioning。

Plan 必须能够表达：

- element membership；
- semantic parent；
- visual grouping；

但不要求 v1 冻结具体 group schema。

---

# 10. Element 最小语义

每个 Element 至少需要能够表达以下语义：

```text
stable id
source / provenance
semantic role
content_ref or data_ref
representation
approximate geometry
z-order
major style
important visual relations
asset request（如适用）
revision state（如适用）
```

不是每个 Element 都必须具有所有字段。

例如纯装饰 Shape 不需要 `content_ref`。

---

# 11. Stable ID

每个可独立重建 Element 必须有稳定 ID。

稳定 ID 用于：

- Plan 编译；
- QA；
- Visual Reviewer 问题定位；
- Revision Patch；
- Accepted Page Plan；
- Final Deck rebuild；
- Evidence 追踪。

Revision Patch 不应通过“第三个蓝色卡片”这种自然语言描述寻找对象。

必须通过：

```text
stable element id
```

定位。

---

# 12. Source / Provenance

Plan 必须能够表达 Element 来自哪里。

常见来源：

```text
Stage 1 semantic object
Stage 1 canonical content
Stage 1 structured data
Stage 2 important visual object
Approved Design visual realization
```

概念示例：

```yaml
id: chart_01
source_ref: stage1.chart_01
data_ref: stage1.data.chart_01
```

复杂视觉：

```yaml
id: hero_illustration
source_ref: stage2.hero_illustration
```

Plan 不复制权威数据，只保存引用关系。

---

# 13. Content Reference

正式文字不应由 Layout Planner 在 Plan 中重新自由生成。

Plan 应优先表达：

```text
content_ref
```

而不是：

```text
重新写一遍正文
```

例如：

```yaml
id: title
content_ref: stage1.content.title
representation: native_text
```

确定性 Compiler 再从权威内容中取得实际文字。

---

# 14. Data Reference

Chart / Table 必须引用 Stage 1 Structured Data。

例如：

```yaml
id: chart_01
data_ref: stage1.data.chart_01
representation: native_chart
```

如果：

```text
data_ref missing
```

则不能：

- OCR；
- 根据设计图估算；
- 使用 raster fallback；
- 用 dummy data。

应进入：

```text
missing_structured_data
→ BLOCK
```

---

# 15. Geometry Contract

每个需要定位的 Element 必须具有**近似可执行几何**。

至少需要表达：

```text
x
y
width
height
```

或语义等价形式。

---

# 16. Geometry Precision

v1 明确：

> **Geometry 的目标是足以完成首轮 PPT 构建，不追求像素级复刻。**

必须保证：

- 页面区域基本正确；
- 大小比例基本正确；
- 视觉重心基本正确；
- z-order 正确；
- 重要 overlap 正确。

允许：

- 轻微位置差异；
- 轻微宽高差异；
- 用户最终手动微调。

---

# 17. Coordinate System

本合同冻结：

> **Plan 必须存在统一、可确定性转换的几何坐标模型。**

本合同不冻结：

- pixel coordinates；
- normalized coordinates；
- PowerPoint inches。

后续 Implementation Benchmark 决定具体表示。

当前偏好：

> 归一化页面坐标优先作为候选方案。

原因：

- 不绑定 Approved Design 分辨率；
- 容易映射到不同 slide size；
- 符合“近似可执行几何”的目标。

但这不是当前 Contract 的强制实现决策。

---

# 18. Z-order

Plan 必须能够表达：

```text
front / back order
```

至少应让 Builder 能够确定：

- 哪些对象在背景之上；
- 哪些对象在内容之后；
- 哪些对象必须位于文字后方；
- 哪些对象不能遮挡正式内容。

具体采用：

```text
z_index
```

还是：

```text
ordered element list
```

由后续 Schema 决定。

---

# 19. Representation

每个可构建 Element 必须有明确重建方式。

v1 目标类别至少包括：

```text
native_text
native_shape
native_connector
native_chart
native_table
svg
raster_asset
```

具体枚举名称后续冻结。

---

# 20. Representation Policy

默认对象策略：

```text
正式文字
→ native_text

基础形状 / 卡片 / panel
→ native_shape

Connector / Arrow
→ native_connector

可恢复平面矢量
→ native_shape / svg

Chart
→ native_chart

Table
→ native_table

复杂插画 / 照片 / 3D / 纹理
→ raster_asset
```

Plan 不允许无理由把：

```text
native-required object
```

降级为 raster。

---

# 21. Style Contract

Canonical Reconstruction Plan 必须保存**主要视觉样式**。

目标是：

> 重建视觉系统，而不是保存 Photoshop 级像素参数。

---

# 22. 主要样式

根据 Element 类型，Plan 应能表达以下主要视觉信息。

## 22.1 Text

例如：

- font family；
- approximate font size；
- weight；
- color；
- alignment；
- line / paragraph alignment；
- major emphasis。

## 22.2 Shape

例如：

- fill；
- stroke；
- corner radius；
- opacity；
- major shadow。

## 22.3 Chart

例如：

- chart type；
- approximate plot layout；
- series visual mapping；
- legend position；
- title / label visibility；
- major colors。

## 22.4 Table

例如：

- header style；
- body style；
- row / column emphasis；
- borders；
- alignment；
- major fills。

---

# 23. Style 不追求的精度

v1 不要求 Agent 精确恢复：

- blur radius；
- every gradient stop；
- subpixel letter spacing；
- tiny glow；
- exact shadow spread；
- photo filter parameters。

如果这些效果无法通过 native style 合理表达，可以：

- 做合理近似；
- 保留在复杂 visual asset 中。

---

# 24. Semantic Relations

Stage 1 已经确认的语义关系不能在 Plan 中重新定义成第二份权威。

例如：

```text
step_1 → step_2 → step_3
```

应优先通过：

```text
relation_ref
```

引用 Stage 1。

---

# 25. Stage 3 Visual Relations

Stage 3 新产生的视觉关系必须由 Plan 表达。

例如：

```text
hero_illustration
behind
step_3
```

例如：

```text
connector_02
visually_connects
step_2
step_3
```

例如：

```text
badge_01
inside
step_1_background
```

典型 Stage 3 relation：

- z-order；
- overlap；
- visual grouping；
- containment；
- visual connection；
- alignment dependency。

---

# 26. Relation Authority Rule

原则：

```text
Stage 1 semantic relation
→ 引用

Stage 3 reconstruction / visual relation
→ Plan 自己记录
```

这样避免同一个语义事实存在两份不同 Source of Truth。

---

# 27. Complex Visual Asset Request

对于：

- 插画；
- 照片；
- 3D；
- texture；
- 无法合理 native reconstruction 的复杂视觉；

Layout Planner 不直接生成最终资产。

Plan 只表达：

> **资产请求（Asset Request）**

---

# 28. Asset Request 最小语义

至少需要表达：

```text
target element id
source = approved_design
crop_required
approximate source region
placement geometry
z-order
safe-crop expectation
```

概念示例：

```yaml
id: hero_illustration

representation:
  type: raster_asset

asset_request:
  source: approved_design
  crop_required: true
  approximate_source_region: ...
```

---

# 29. Runtime Asset Binding

实际裁切完成后，确定性 Runtime 再产生：

```text
asset_id
file path
hash
actual crop region
dimensions
```

因此原则是：

```text
Planner Plan
→ 描述需要什么资产

Runtime Artifact
→ 记录最终得到了哪个资产
```

Agent 不负责虚构：

```text
final asset path
hash
```

---

# 30. Safe Crop Gate

任何 raster asset request 必须满足 Safe Crop Policy。

不得裁切：

- required canonical text；
- native-required Chart；
- native-required Table；
- 需要保持 native 的其他 semantic object；
- 会形成明显不可接受 seam 的区域；
- 需要模型重新生成缺失部分才能成立的视觉。

如果无法满足：

```text
unsafe_crop
→ BLOCK
```

Stage 3 不重新生图。

---

# 31. Revision Model

Canonical Reconstruction Plan 支持有界定向修订。

默认：

```text
Canonical Plan v1
+
Revision Patch
        ↓
Deterministic Patch Apply
        ↓
Canonical Plan v2
```

Layout Planner 在定向修订模式下不默认重写整份 Plan。

---

# 32. Revision Patch

Revision Patch 不是新的 Canonical Plan。

它只是：

> **对当前 Canonical Plan 的有界修改请求。**

Patch 至少需要能够表达：

```text
base plan version
target element ids
allowed changes
necessary linked element changes
revision reason
review issue reference
```

---

# 33. Patch Scope

Patch 可以是：

```text
single element
local group
page-level replan
```

但：

> page-level patch / replan 是最后手段。

如果 Reviewer 只指出：

```text
chart_01
```

Patch 不得无理由修改：

```text
title
hero
step_1
step_2
```

---

# 34. Locked Elements

Canonical Plan / Revision State 必须能够表达：

```text
locked element
```

含义：

> 该对象当前已被接受，Revision Patch 默认不能修改。

只有在：

```text
修复目标对象必然要求连带修改
```

时，才允许扩大 scope。

并且必须记录原因。

---

# 35. Deterministic Patch Apply

Revision Patch 不直接成为新的 runtime source。

必须通过确定性程序：

```text
Plan v1
+
Patch
↓
Validate Patch Scope
↓
Apply Patch
↓
Plan v2
```

确定性程序应检查：

- target id 是否存在；
- locked element 是否被非法修改；
- representation 是否违反 policy；
- content_ref / data_ref 是否被非法改变；
- patch scope 是否越界。

---

# 36. Plan Versioning

Canonical Reconstruction Plan 必须具备版本语义。

例如：

```text
v1
→ initial plan

v2
→ targeted revision 1

v3
→ targeted revision 2
```

具体版本格式不冻结。

---

# 37. Provenance

Plan 必须具备 provenance 语义。

至少需要能够追踪：

- 基于哪个 Stage 1 内容 / 结构版本；
- 基于哪个 Stage 2 visual object set；
- 基于哪个 Approved Design；
- 前一个 Plan 版本；
- 哪次 Revision Patch 产生当前 Plan。

---

# 38. Hash / Artifact Binding

本合同建议但不冻结具体字段形式：

```text
artifact hash
```

例如：

```yaml
provenance:
  approved_design_hash: ...
  stage1_structure_hash: ...
  previous_plan_hash: ...
```

目的：

> 确保 Build、Review、Accepted Page、Final Deck 使用的是同一组输入与 Plan 版本。

后续正式 Schema 可决定使用 SHA-256 或其他一致性机制。

---

# 39. Plan 与 Build Evidence 的关系

必须能够建立：

```text
Plan version
↓
Build
↓
Rendered Slide
↓
QA
↓
Visual Review
```

的一一绑定。

Reviewer Evidence 不得在 Plan 更新后自动继续视为有效。

例如：

```text
Plan v1
→ Render A
→ Review PASS

Plan v2
```

则：

```text
Render A / Review PASS
```

不能自动证明：

```text
Plan v2
```

已经通过。

---

# 40. Plan 与现有 Runtime Artifact

布局规划代理不直接维护：

```text
layout.json
crops.json
asset_manifest.json
```

而是：

```text
Canonical Reconstruction Plan
        ↓
Deterministic Plan Compiler
        ├─ layout.json
        ├─ crops.json
        └─ asset_manifest.json
```

这样现有 Runtime 可以逐步兼容，而 Agent 不被历史 Artifact 格式绑定。

---

# 41. Plan Compiler 的职责

确定性 Plan Compiler 负责：

- Schema / contract validation；
- stable ID validation；
- content_ref validation；
- data_ref validation；
- representation policy validation；
- geometry normalization；
- z-order normalization；
- relation resolution；
- asset request generation；
- legacy runtime artifact generation。

Plan Compiler 不调用 LLM。

---

# 42. Plan Compiler 不负责什么

它不得：

- 重新设计页面；
- 重新决定 representation；
- 猜缺失的数据；
- 重写文字；
- 修改语义结构；
- 自动把 native-required object 降级成 raster。

发现非法状态时：

```text
→ validation error / BLOCK
```

---

# 43. Native Chart Contract

只要 Element 语义为正式 Chart：

```text
representation = native_chart
```

必须具有：

```text
data_ref
```

并允许表达主要 Chart visual settings。

不得：

- crop chart screenshot；
- OCR chart data；
- shape-based fake chart 代替正式 Chart。

---

# 44. Native Table Contract

只要 Element 语义为正式 Table：

```text
representation = native_table
```

必须具有：

```text
data_ref
```

并允许表达主要 Table style。

不得：

- crop table screenshot；
- shape + text 模拟完整 table body。

---

# 45. Failure State

Canonical Reconstruction Plan 允许显式失败，不要求始终生成可执行计划。

至少保留以下 failure semantics：

```text
grounding_incomplete
authority_conflict
missing_structured_data
unsafe_crop
unsupported_reconstruction
```

发生这些状态时：

> 不生成伪造的可执行 Plan。

---

# 46. `grounding_incomplete`

含义：

> 必需对象无法在 Approved Design 中可靠完成视觉位置对齐。

处理：

```text
BLOCK / return upstream review
```

---

# 47. `authority_conflict`

含义：

> Stage 1 semantic authority 与 Approved Design 存在无法自动解决的真实结构冲突。

处理：

```text
BLOCK
```

---

# 48. `missing_structured_data`

含义：

> Native Chart / Table 所需权威数据缺失。

处理：

```text
BLOCK
→ Stage 1
```

---

# 49. `unsafe_crop`

含义：

> 复杂 visual 无法安全独立裁切。

处理：

```text
BLOCK
→ Stage 2
```

---

# 50. `unsupported_reconstruction`

含义：

> 当前 representation policy 无法同时满足编辑性与合理视觉效果。

处理：

```text
BLOCK
→ Stage 2 / design adjustment
```

---

# 51. Accepted Page Plan

页面通过：

```text
Structural / Editability QA
+
Visual Reviewer
```

后，当前 Canonical Reconstruction Plan 可进入 Accepted 状态。

Accepted Page Plan 应绑定：

- accepted plan version；
- validated asset references；
- accepted render；
- structural QA evidence；
- visual review evidence。

---

# 52. Accepted Asset Immutability

对于已通过视觉审核的 raster asset：

Final Deck 构建必须复用：

```text
same asset identity
+
same validated asset content
```

不能在 Final Deck 阶段重新裁一次。

否则：

```text
单页 Reviewer 审核的资产
≠
Final Deck 实际资产
```

会失去 Evidence 的有效性。

---

# 53. Final Deck Construction

所有 Accepted Page Plan：

```text
Accepted Page Plan 1
Accepted Page Plan 2
...
Accepted Page Plan N
        ↓
Shared Builder
        ↓
Final Deck
```

Final Deck 不以：

```text
per-slide PPTX merge
```

作为主权威路径。

---

# 54. Final Deck Drift

Final Deck 构建后应进行低成本确定性 Drift Check：

```text
Final Deck slide render
vs
Accepted single-page render
```

无明显 drift：

```text
→ delivery
```

有明显 drift：

```text
→ targeted investigation / visual re-review
```

不默认重新跑 Whole-Deck Visual Reviewer。

---

# 55. Canonical Plan 最小概念示例

以下仅展示语义，不冻结最终字段名或 Schema：

```yaml
page:
  id: slide_03

plan:
  version: 2

elements:

  - id: title
    source_ref: stage1.title
    content_ref: stage1.content.title
    role: title

    geometry:
      x: ...
      y: ...
      width: ...
      height: ...

    representation:
      type: native_text

    style:
      font_family: ...
      font_size: ...
      font_weight: ...
      color: ...
      alignment: ...

    revision:
      locked: true

  - id: chart_01
    source_ref: stage1.chart_01
    data_ref: stage1.data.chart_01
    role: chart

    geometry:
      x: ...
      y: ...
      width: ...
      height: ...

    representation:
      type: native_chart

    style:
      chart_type: ...
      legend_position: ...
      major_colors: ...

  - id: hero_illustration
    source_ref: stage2.hero_illustration
    role: complex_visual

    geometry:
      x: ...
      y: ...
      width: ...
      height: ...

    representation:
      type: raster_asset

    asset_request:
      source: approved_design
      crop_required: true
      approximate_source_region: ...

relations:

  - type: behind
    from: hero_illustration
    to: step_3

revision:
  base_version: 1

provenance:
  stage1_ref: ...
  stage2_visual_ref: ...
  approved_design_ref: ...
  previous_plan_ref: ...
```

---

# 56. Revision Patch 概念示例

```yaml
patch:
  base_plan_version: 2

  targets:
    - chart_01

  reason:
    review_issue_ref: issue_03

  changes:
    chart_01:
      geometry:
        width: ...
        y: ...

  locked_elements:
    preserve:
      - title
      - step_1
      - step_2
      - hero_illustration
```

确定性程序：

```text
Plan v2
+
Patch
↓
Validate
↓
Plan v3
```

---

# 57. v1 明确不冻结的事项

本合同暂不冻结：

- 最终文件名；
- 最终 JSON Schema；
- exact field names；
- pixel vs normalized coordinate；
- absolute vs relative z-index implementation；
- exact representation enum names；
- exact style schema；
- asset directory layout；
- hash algorithm；
- revision patch file format；
- maximum revision count；
- current Runtime migration details；
- PptxGenJS / COM / Open XML / Aspose backend choice。

这些进入 Benchmark / ADR / Implementation 后再冻结。

---

# 58. 冻结决策摘要

| 项目 | v1 决策 |
|---|---|
| Plan 定位 | Stage 3 唯一规范化重建计划 |
| Plan 粒度 | 每页一份 |
| Element 粒度 | 独立构建 / 定位 / 编辑 / 裁切 / 层级控制才独立成 Element |
| Stable ID | 必须 |
| 正式文字 | content_ref 引用 Stage 1 |
| Chart / Table 数据 | data_ref 引用 Stage 1 |
| Geometry | 必须表达近似 bbox 语义 |
| Geometry 精度 | 首轮可执行，不追求像素级 |
| 坐标单位 | Contract 不冻结 |
| Z-order | 必须表达 |
| Representation | native text / shape / connector / chart / table / svg / raster 等语义 |
| Style | 保存主要视觉样式，不追求像素级参数 |
| Stage 1 Relations | 引用，不复制第二份权威 |
| Stage 3 Visual Relations | Plan 负责记录 |
| Complex Visual | Asset Request → Runtime 生成最终 asset |
| Crop | Planner 给近似需求，Runtime 绑定最终 crop/path/hash |
| Revision | Revision Patch |
| Patch Apply | 确定性程序执行 |
| 已通过 Element | 默认 locked |
| Plan Version | 必须 |
| Provenance | 必须 |
| Runtime 兼容 | 由 deterministic compiler 负责 |
| Failure | 允许 BLOCK，禁止硬猜 |
| Accepted Page | 绑定 accepted plan + assets + QA + review evidence |
| Final Deck | Shared Builder 使用 Accepted Page Plans |

---

# 59. 最终工作流

```text
Stage 1 Canonical Content
Stage 1 Semantic Structure
Stage 1 Structured Data
Stage 2 Important Visual Objects
Approved Design
        ↓
Layout Planner
        ↓
Canonical Reconstruction Plan v1
        ↓
Deterministic Plan Validation
        ↓
Plan Compiler
        ↓
Runtime Artifacts
        ↓
PPT Build
        ↓
Structural / Editability QA
        ↓
Visual Reviewer
        │
        ├─ PASS
        │    ↓
        │  Accepted Page Plan
        │
        ├─ PASS_WITH_MINOR_DIFFERENCES
        │    ↓
        │  Accepted Page Plan
        │
        ├─ REVISION_REQUIRED
        │    ↓
        │  Revision Patch
        │    ↓
        │  Deterministic Patch Apply
        │    ↓
        │  Canonical Plan v2
        │    ↓
        │  Rebuild + QA + Re-review
        │
        └─ BLOCK
             ↓
          Return Stage 1 / Stage 2

All Accepted Page Plans
        ↓
Shared Builder
        ↓
Final Deck
        ↓
Deterministic Deck QA
        ↓
Final Build Drift Check
        ↓
Delivery
```

---

# 60. 结论

Canonical Reconstruction Plan 应成为 Visual-first Stage 3 中连接 Agent Reasoning 与 Deterministic PPT Runtime 的稳定中间合同。

它的职责不是保存所有原始内容，也不是直接描述底层 PPTX 实现，而是：

> **用稳定 ID、权威引用、近似几何、主要视觉样式、重建方式、视觉关系、资产请求、修订状态和 provenance，完整表达“这一页应如何被重建”，并让后续编译、构建、审核、定向修订和 Final Deck 重建都围绕同一份规范化计划运行。**
