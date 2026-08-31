# Stage 3 Guidance：已确认设计图 → 高保真可编辑 PowerPoint

> **Status**：Working Guidance / Pre-ADR Target Design  
> **Document type**：Stage 3 Guidance（Stage 3 目标指导）  
> **Last updated**：2026-08-31  
> **Runtime authority**：非运行权威；不覆盖 Accepted ADR、正式 `SKILL.md`、现有 Runtime 或当前 Schema。  
> **Decision dependency**：Stage 2 真实图片 Benchmark 仍是进入新 ADR / Implementation 的前置 Gate。  
> **Scope**：冻结 Stage 3 的职责、Authority、Planner 输入模型、对象重建原则、单页验收、Final Deck Assembly 与最终 QA；不冻结具体 CLI、函数、最终 JSON Schema 或实现算法。

---

# 1. Stage 3 的目标

Stage 3 的任务是：

> **将 Stage 2 中用户已经确认的最终设计图，高保真地重建为具有 Useful Editability 的 PowerPoint。**

Stage 3 是 reconstruction，不是 redesign。

目标链路：

```text
Stage 1 Approved Content
+ Stage 1 Wireframe
+ Stage 2 Visual Design Spec
        ↓
Cross-stage Handoff Preparation
        ↓
Reconstruction Context（候选持久化形式）
        +
用户确认后的最终设计图
        +
固定 Planner Prompt
        +
Existing Reconstruction Policy
        ↓
Planner Agent
        ↓
Canonical Reconstruction Plan
        ↓
Deterministic Validation / Compilation
        ↓
Existing Single-Slide Reconstruction Runtime
        ↓
Page Structural / Editability QA
        ↓
Page Visual Review
        ↓
Accepted Page Plan

所有 Accepted Page Plans
        ↓
Shared Builder
        ↓
One Final Deck.pptx
        ↓
Deterministic Deck QA
        ↓
PASS → Delivery

仅在明确风险时：
        ↓
Conditional Deck-level Visual Review
```

---

# 2. Stage 3 的职责边界

## 2.1 Stage 3 必须做什么

Stage 3 必须：

- 保留 Stage 1 已确认的正式文字、数字、数据和逻辑关系；
- 以 Stage 1 Wireframe 作为页面 topology / region relationship / reading direction 的结构 Authority；
- 以用户确认后的最终设计图作为已确认结构范围内的最终视觉实现 Authority；
- 复用现有 Reconstruction-aware Hybrid 原则决定 Native / SVG / Raster；
- 将复杂视觉作为独立 Asset，而不是整页栅格化；
- 将 Chart 重建为 Native PowerPoint Chart；
- 将 Table 重建为 Native PowerPoint Table；
- 对每页执行结构 / 可编辑性 QA 与视觉 Fidelity Review；
- 只冻结通过单页 Gate 的页面；
- 最终由 Shared Builder 一次生成完整 Deck；
- 对 Final Deck 执行低成本确定性 QA。

## 2.2 Stage 3 不允许做什么

Stage 3 不允许：

```text
重新写文案
重新规划 Storyline
重新设计 Layout / topology
因为更容易重建而修改已确认视觉
用 OCR 覆盖 Stage 1 正式文字或数据
整页 PNG 冒充 editable PPT
把正式文字卡片整体截图
把 Chart 或 Table 截图代替 Native 对象
重新调用图片模型生成“相似”的复杂视觉
```

如果 Stage 1 / Stage 2 的已确认 Authority 之间发生真实结构冲突，Stage 3 不自行裁决：

> **Handoff invalid → 返回 Stage 2 修正。**

---

# 3. Authority 模型

| 信息类型 | Authority |
|---|---|
| 正式文字、数字、单位、专名、结论 | Stage 1 Approved Content |
| Chart / Table 原始数据 | Stage 1 Structured Data |
| 页面 topology、区域关系、阅读方向、流程关系 | Stage 1 Wireframe |
| 最终位置、比例、留白、颜色、字体视觉、阴影、Overlap、视觉层级 | 用户确认后的最终设计图 |
| 图片中难以稳定判断的设计意图 | Stage 2 Visual Design Spec |
| Native / SVG / Raster 决策 | Existing Reconstruction Policy（当前为 `element-classification.md`） |

冲突处理：

```text
Final Design 中的文字 ≠ Stage 1 Content
→ Stage 1 Content

Final Design 中的数据 ≠ Stage 1 Structured Data
→ Stage 1 Structured Data

Wireframe 与 Final Design 只是视觉细化差异
→ topology 听 Wireframe，realized geometry 听 Final Design

Wireframe 与 Final Design 出现真实 topology 冲突
→ Handoff invalid，返回 Stage 2

Visual Design Spec 与 Final Design 冲突
→ Final Design 优先

Final Design 中连接关系不清
→ 使用 Wireframe 已确认 relation
```

一句话：

> **Stage 1 决定“是什么、怎么组织”；Final Design 决定“最后具体长什么样”；Visual Spec 只提供辅助解释。**

---

# 4. Cross-stage Handoff 的前置要求

这是 Stage 3 能否稳定实现的关键。

Stage 3 **不能假设程序可以从自由 Markdown、ASCII Wireframe 或自然语言 Visual Spec 中确定性推导所有关系**。

因此，正式实现 Stage 3 之前，上游 Handoff 至少需要暴露一组最小机器可读字段。

## 4.1 Stage 1 最小机器可读字段

Stage 1 应能提供：

```text
stable content IDs
region IDs
region membership
confirmed relations / topology
structured Chart data
structured Table data
```

例如：

```yaml
regions:
  - id: main_flow
    members: [step_1, step_2, step_3]

relations:
  - type: flow
    from: step_1
    to: step_2
  - type: flow
    from: step_2
    to: step_3
```

Stage 1 仍可保留 Markdown / ASCII Wireframe 供人阅读；机器可读字段只服务跨阶段稳定传递。

## 4.2 Stage 2 最小机器可读字段

Stage 2 Visual Spec 应能为需要 Stage 3 使用的视觉对象提供稳定 ID 与必要 hint，例如：

```yaml
visual_objects:
  - id: hero_illustration
    role: complex_visual

reconstruction_hints:
  - target: hero_illustration
    relation: intentional_overlap
    with: step_3
```

不要求 Stage 2 输出最终重建坐标。

## 4.3 Handoff Preparation 的职责

只有在上述上游字段存在后，Handoff Preparation 才可以是 deterministic：

```text
Validate
↓
Select
↓
Normalize
↓
Combine
```

它不负责：

```text
从自然语言猜关系
从 ASCII 猜 object IDs
从 Final Design OCR 正式内容
决定 Native / SVG / Raster
决定最终坐标
```

因此此前讨论中的 “Deterministic Context Compiler” 应理解为：

> **确定性整理已结构化的上游事实，而不是用程序或 LLM 重新理解自由文本。**

---

# 5. Reconstruction Context

`Reconstruction Context` 是一个 Stage 3 Planner-facing 的候选中间事实包。

它的职责只有一个：

> **保存 Planner 不应该重新从最终设计图猜测的已知事实。**

建议最小语义结构：

```text
identity
canonical_content
structured_data
semantic_structure
relations
reconstruction_hints
```

它不保存：

```text
最终 x / y / w / h
最终 Crop
最终字体大小
最终颜色
最终 Native / SVG / Raster 决策
```

正式边界：

```text
Context
= 已知事实

Planner
= 重建决策

Plan
= 执行规格
```

`Reconstruction Context` 的最终文件名和 JSON Schema **不在本 Guidance 中冻结**；`reconstruction-context.json` 仅作为候选持久化形式。

---

# 6. Planner Agent Contract

## 6.1 Planner 输入模型

Planner Agent 应接收：

```text
用户确认后的最终设计图
+
Reconstruction Context
+
固定 Planner Prompt
+
Existing Reconstruction Policy
+
Output Schema
```

其中：

| 输入 | 作用 |
|---|---|
| Final Design | 最终视觉参考 |
| Reconstruction Context | 已确认内容、数据、结构、关系和必要设计提示 |
| Planner Prompt | 定义任务、边界、Authority 使用规则 |
| Existing Reconstruction Policy | 定义 Native / SVG / Raster 决策 |
| Output Schema | 约束 Canonical Reconstruction Plan |

## 6.2 Planner Prompt 只负责少量稳定规则

Prompt 不应发展成 Mega Prompt。

只需要明确：

1. 你是 Stage 3 Reconstruction Planner；
2. Reconstruction，不是 Redesign；
3. Final Design 是视觉参考；
4. Context 是 canonical content / data / topology 的事实来源；
5. 不得通过 OCR 覆盖 canonical content / data；
6. 对象表示必须遵守现有 Reconstruction Policy；
7. 只输出符合 Output Schema 的 Canonical Plan。

完整 Prompt 文案、Few-shot、token 优化属于 Implementation / Prompt Engineering。

---

# 7. Canonical Reconstruction Plan

Planner 的正式输出原则上应收敛为：

> **一个 Canonical Reconstruction Plan。**

它至少应能表达：

```text
slide identity
elements
semantic/data references
object type
representation
geometry
style
z-order
relations
asset instructions
```

这样 Agent 不需要直接维护多份彼此引用的 Runtime Artifact。

现有：

```text
layout.json
crops.json
asset_manifest.json
```

可以在第一阶段由确定性 Plan Compiler 从 Canonical Plan 派生，以兼容现有 Runtime。

最终 Plan 文件名、字段和 Schema 不在本 Guidance 中冻结；`reconstruction-plan.json` 只是当前候选形式。

---

# 8. Coordinate Policy

Planner 的视觉几何建议使用：

> **最终设计图原始 Pixel Coordinate Space。**

例如：

```text
box_px = [x, y, width, height]
```

再由确定性程序转换为 PowerPoint 坐标。

原因：

- Planner 直接面对的就是最终设计图；
- 减少 Agent 自己做单位换算；
- 更容易 Debug；
- QA 结果更容易映射回 Final Design。

是否最终采用该字段形式，由 Implementation Benchmark 冻结。

---

# 9. Object Reconstruction Policy

Stage 3 继续继承现有 Reconstruction-aware Hybrid 原则。

目标策略：

```text
Formal Text
→ Native PowerPoint Text

Basic Shape / Card / Panel
→ Native PowerPoint Shape

Line / Arrow / Connector
→ Native PowerPoint Line / Connector

Recoverable Flat Vector
→ Native Shape / Sanitized SVG

Complex Illustration / Photo / Texture / 3D
→ Raster Asset cropped from Final Design

Chart
→ Native PowerPoint Chart

Table
→ Native PowerPoint Table
```

禁止：

```text
Whole-slide rasterization
Text-bearing card rasterization
Chart rasterization
Table rasterization
```

---

# 10. Complex Visual Asset Policy

已确认决策：

> **复杂视觉直接从用户确认后的最终设计图中 Crop；Stage 3 不重新生图。**

流程：

```text
Final Design
↓
Planner 标记 Complex Visual
↓
Safe Crop Check
↓
Crop
↓
Validated Local Asset
↓
按 Plan 放回 PPT
```

适用：

- 3D 插画；
- 照片；
- complex texture；
- polished visual；
- 难以合理 Native 重建的复杂装饰。

## 10.1 Safe Crop Gate

复杂视觉只有满足以下条件才允许直接 Crop：

- 不包含 required canonical text；
- 不包含必须保持 Native 的 Chart / Table；
- 不包含不应被一起 Raster 的 semantic object；
- Crop 边界不会造成明显不可接受的背景接缝；
- 不需要通过“补画”才能恢复被遮挡部分。

如果不能安全 Crop：

```text
Complex Visual
↓
Safe Crop = No
↓
Stage 3 BLOCK
↓
Return to Stage 2
```

Stage 3 不通过重新生图绕过这一问题。

## 10.2 正式文字不得随 Asset 一起 Raster

如果：

```text
Complex Illustration + Canonical Label
```

应：

```text
Crop Illustration
+
Native Text Label
```

而不是整块截图。

---

# 11. Native Chart Policy

已确认决策：

> **Chart 必须重建为 Native PowerPoint Chart。**

目标：

```text
Stage 1 Authoritative Chart Data
+
Stage 2 Final Design
↓
Native PowerPoint Chart
```

用户应能够双击图表并修改：

- data；
- series；
- chart type；
- formatting。

不允许：

```text
Shapes 模拟完整 Chart
Chart Crop PNG
```

## 11.1 Chart 的跨阶段前置合同

只要页面出现 Chart：

### Stage 1 必须提供

```text
chart type / semantic intent（如已知）
categories
series
values
labels / units
```

至少要保证 Native Chart 所需 authoritative data 完整。

### Stage 2 必须遵守

> **Native-semantic compatibility constraint**

也就是：

- 可以美化；
- 可以调整配色、线宽、标签、图例、留白；
- 但不能批准一个明显超出 PowerPoint Native Chart 合理表达能力、却又要求 Stage 3 原生高保真恢复的设计。

例如应避免把必须 Native 的 Chart 设计成：

```text
3D 异形柱体
强透视
复杂材质
不可由 Native Chart 近似的特殊结构
```

如果 Stage 2 设计无法同时满足 Native Chart 和合理视觉 Fidelity：

> **应在 Stage 2 解决，而不是 Stage 3 静默降级。**

如果 Stage 1 authoritative data 缺失：

> **Stage 3 BLOCK，不 OCR 猜数据，不 Raster fallback。**

---

# 12. Native Table Policy

已确认决策：

> **Table 必须重建为 Native PowerPoint Table。**

目标：

```text
Stage 1 Authoritative Table Data
+
Stage 2 Final Design
↓
Native PowerPoint Table
```

用户应可以编辑：

- cells；
- rows；
- columns；
- styles。

不允许：

```text
Shapes + Text 模拟整个 Table
Table Crop PNG
```

允许在 Native Table 外围增加必要的 Native Shape 作为视觉补偿，但表格主体必须保持 Native Table 语义。

## 12.1 Table 的跨阶段前置合同

只要页面出现 Table：

### Stage 1 必须提供

```text
rows
columns
cell values
header structure
必要的 merge semantics（如存在）
```

### Stage 2 必须遵守

> **Native-semantic compatibility constraint**

可以设计：

- cell fill；
- border；
- typography；
- emphasis；
- spacing；
- surrounding decoration。

但不应批准一个必须依赖非原生结构才能成立、同时又要求 Stage 3 原生高保真恢复的 Table。

如果 Stage 1 authoritative table data 缺失：

> **Stage 3 BLOCK，不 OCR 猜数据，不 Raster fallback。**

---

# 13. Deterministic Boundary

Planner 只负责产生 Canonical Reconstruction Plan。

Agent 输出后进入确定性边界：

```text
Canonical Plan
↓
Normalize
↓
Validate
↓
Compile
↓
Existing Runtime Artifacts
```

确定性程序负责：

- Schema validation；
- stable ID validation；
- content / data reference validation；
- relation validation；
- geometry boundary validation；
- representation policy validation；
- Raster prohibition validation；
- Native Chart / Table policy validation；
- Runtime artifact generation。

具体模块名是否叫 `Plan Normalizer / Plan Validator / Plan Compiler` 不在本 Guidance 中冻结。

核心原则只有：

> **Agent 负责需要视觉理解和重建判断的部分；能够确定性验证、转换和执行的工作由程序完成。**

---

# 14. Page Reconstruction Workflow

每页独立执行：

```text
Final Design
+
Reconstruction Context
↓
Planner Agent
↓
Canonical Reconstruction Plan
↓
Deterministic Validation / Compilation
↓
Asset Crop
↓
PPT Build
↓
Render
↓
Structural / Editability QA
↓
Visual Reviewer
↓
PASS
```

失败分类：

```text
Canonical Content / Data Failure
→ BLOCK

Structural / Editability Failure
→ Targeted Plan / Builder Fix

Visual Fidelity Failure
→ Targeted Planner Revision / Patch

Unsafe Crop
→ BLOCK and Return to Stage 2
```

已通过页面不因为其他页面失败而重跑。

---

# 15. Accepted Page Plan

已确认决策：

> **最终 Deck Assembly 以 Accepted Page Plans 为核心，而不是合并单页 PPTX。**

但 Accepted Page Plan 不能只理解成一份 JSON。

真正被接受的是：

```text
Accepted Canonical Plan
+
Immutable Validated Asset References
+
Accepted Single-page Render / Review Evidence
```

因此每个被引用的 Asset 应至少绑定：

```text
asset_id
path / logical URI
hash
```

最终 Shared Builder 必须使用：

> **单页 QA / Visual Review 时已经验证过的同一批 Asset。**

禁止：

```text
Page Review 用 asset-v1
↓
Final Build 时重新 Crop 成 asset-v2
```

否则 Final Deck 已不再等价于单页已审核结果。

---

# 16. Final Deck Assembly

已确认决策：

> **Accepted Page Plans → Shared Builder → One Final PPTX**

即：

```text
S01 Accepted Page Plan ─┐
S02 Accepted Page Plan ─┤
S03 Accepted Page Plan ─┤
S04 Accepted Page Plan ─┘
             ↓
         Shared Builder
             ↓
       Final Deck.pptx
```

不采用：

```text
page01.pptx
page02.pptx
page03.pptx
↓
COM Merge / PPTX Merge
```

这样避免：

- slide relationship merge；
- media relationship repair；
- COM copy-slide；
- Theme / Master 合并污染。

---

# 17. Final Deck QA

已确认决策：

> **必跑低成本 Deterministic Deck QA；Deck-level Visual Review 只在明确风险时触发。**

## 17.1 必跑 Deterministic Deck QA

至少检查：

- PPTX 可打开 / 可保存 / 可 Roundtrip；
- 页数正确；
- 页序正确；
- 页面尺寸一致；
- 无空白页；
- canonical text 仍为 Native；
- Chart 仍为 Native Chart；
- Table 仍为 Native Table；
- validated assets 引用与 hash 正确；
- 无明显越界 / 溢出；
- Accepted Page 未丢失。

## 17.2 Final Build Drift Check

为了避免每次都重新做整套视觉 Agent Review，建议增加低成本比较：

```text
Final Deck 某页 Render
vs
该页 Accepted Single-page Render
```

如果 Final Shared Build 与已审核单页 Render 基本一致：

```text
→ 不触发额外 Deck Visual Review
```

如果出现明显 drift：

```text
→ 标记 final_build_visual_drift
→ 触发 Targeted Investigation / Visual Review
```

具体图像差异算法与阈值在 Implementation 阶段冻结。

## 17.3 Conditional Deck-level Visual Review

只在以下情况触发：

- Deterministic Deck QA 有风险；
- Final Build Drift Check 异常；
- 存在 Page Warning；
- 某页经历 Recovery / Patch 后仍有一致性风险；
- 正式 Release / Field Validation。

正常路径：

```text
All Pages Accepted
+
Final Deck Build
+
Deterministic Deck QA PASS
+
No Final Build Drift
↓
Delivery
```

---

# 18. 与当前 Runtime 的复用关系

Stage 3 不新建第三套 Reconstruction Runtime。

目标原则：

> **Thin Stage 3 Orchestration + Existing Single-Slide Reconstruction Closure + Shared Builder**

应优先复用现有：

```text
Asset Processing
PPT Build
PowerPoint Render
Structural QA
Visual Reviewer
Targeted Patch / Recovery
Shared Slide Builder
Multi-page Build / Delivery QA 基础
```

Stage 3 新增职责集中在：

```text
Cross-stage Handoff Preparation
Planner Context
Canonical Reconstruction Plan
Plan Validation / Compilation
Accepted Page Plan Record
Final Shared Build
Native Table 支持
Native Chart 全链一致性修复
```

---

# 19. Current Capability 与 Target Capability 必须分开

本 Guidance 描写的是目标 Stage 3。

## 19.1 当前可复用基础

当前仓库已有：

- Single-Slide Planner / Reconstruction workflow；
- Crop / SVG 资产链；
- shared slide builder；
- Text / Shape / Line / Image build；
- Native Chart builder 基础；
- PowerPoint Render；
- Structural QA；
- Visual Reviewer；
- Recovery / Review Gate；
- Multi-page direct build 与 Deck QA 基础。

## 19.2 后续 Implementation 需要补齐 / 核验

包括但不限于：

```text
Stage 1 machine-readable topology handoff
Stage 1 authoritative Chart / Table structured data contract
Stage 2 stable visual object IDs / reconstruction hints
Stage 2 Native Chart / Table compatibility constraints
Planner Stage 3 input contract
Canonical Reconstruction Plan contract
Plan validation / compilation
Accepted Page asset immutability
Native Table first-class Builder / Schema / QA
Native Chart Planner / QA / Contract 一致性
Final Shared Build 对 Accepted Page Plans 的消费
Final Build Drift Check
Conditional Deck Visual Review trigger
```

这些不能在本 Guidance 中描述为“已经实现”。

---

# 20. Hard Failure / Block Rules

Stage 3 不通过静默降低编辑性来“假装成功”。

以下情况必须 Block：

```text
Canonical Text 被修改
Canonical Data 被修改
Chart 被 Raster
Table 被 Raster
整页被 Raster
正式文字卡片被整体 Raster
Native Chart / Table 缺少 authoritative data 却通过 OCR 猜测
Wireframe 与 Final Design 出现真实 topology 冲突
Complex Visual 无法 Safe Crop
Final Deck 使用了未经 Page Review 的新 Asset
Final Deck 丢失 Accepted Page
PowerPoint Roundtrip 失败
```

复杂视觉使用独立 Raster Asset：

> **不是 degradation。**

这是正式 Hybrid Policy 的一部分。

---

# 21. Stage 3 成功标准

Stage 3 必须同时满足：

## 21.1 Content Integrity

```text
Stage 1 Canonical Content / Data
=
Final PPT 中正式内容 / 数据
```

## 21.2 Useful Editability

```text
Text → Native Text
Basic Structure → Native Shape / Connector
Chart → Native PowerPoint Chart
Table → Native PowerPoint Table
Complex Visual → Independent validated Asset
```

不存在 Whole-slide Raster Hack。

## 21.3 Visual Fidelity

```text
Rendered Page
≈
用户确认后的最终设计图
```

允许：

- 微小阴影差异；
- 渐变细节差异；
- 像素级偏差；
- PowerPoint Native Chart / Table 与 Stage 2 设计之间不可避免的小幅渲染差异。

不允许：

- 明显 Layout 漂移；
- 错误层级；
- 错误连接；
- 错误裁切；
- 比例失真；
- 关键视觉丢失。

## 21.4 Final Deck Validity

最终 Deck：

- Microsoft PowerPoint 可打开；
- 可保存；
- 可重新渲染；
- 页数 / 页序正确；
- 所有页面来自 Accepted Page Plans；
- 使用单页已验证的 immutable assets；
- Deterministic Deck QA 通过。

---

# 22. 本 Guidance 不冻结的实现细节

暂不冻结：

```text
完整 planner.md 文案
Few-shot 示例
Reconstruction Context 最终文件名 / JSON Schema
Canonical Reconstruction Plan 最终文件名 / JSON Schema
Normalizer / Validator / Compiler 的实际模块名
函数 / CLI 设计
Crop 算法
Image diff 算法与阈值
最大 Revision 次数
并发数
Cache Key
COM Lock
Native Chart 具体样式映射
Native Table 具体样式映射
Deck Visual Reviewer Prompt
Trigger 数值阈值
```

这些应在：

```text
Stage 2 Benchmark
↓
Decision
↓
Proposal ADR
↓
ADR Accepted
↓
Implementation Plan
```

之后结合真实代码与证据冻结。

---

# 23. 已确认决策摘要

| # | 决策 | 已确认方案 |
|---|---|---|
| ① | Planner 输入 | 上游已知事实先形成机器可读 Reconstruction Context；再与最终设计图、固定 Planner Prompt、现有 Reconstruction Policy 和 Output Schema 一起输入 Planner Agent |
| ② | 复杂视觉 | 从用户确认后的最终设计图 Safe Crop；不重新生图；无法安全裁切则返回 Stage 2 |
| ③ | Final Deck Assembly | Accepted Page Plans + 已验证 immutable assets → Shared Builder → One Final PPTX |
| ④ | Chart / Table | Chart → Native PowerPoint Chart；Table → Native PowerPoint Table；Stage 1 必须保留 authoritative structured data，Stage 2 必须遵守 Native compatibility constraint |
| ⑤ | Final Deck QA | 必跑 Deterministic Deck QA + Final Build Drift Check；Deck-level Visual Review 仅在风险或 Release / Field Validation 时触发 |

---

# 24. Guidance 结论

Stage 3 的核心不是再建一套 PPT Runtime，而是：

> **利用 Stage 1 / Stage 2 已确认的内容、结构、数据与视觉证据，把现有单页重建能力升级为一个 context-aware、plan-driven、可被多页统一组装的高保真重建阶段。**

核心原则：

```text
已知事实
→ 上游结构化并确定性传递，不让 Agent 重新猜

需要视觉判断
→ Planner Agent

能够确定性验证 / 转换 / 执行
→ Runtime

复杂视觉
→ Safe Crop from Approved Final Design

Chart / Table
→ Native semantic objects

单页通过
→ Freeze Accepted Plan + validated immutable assets

整套构建
→ Shared Builder

最终质量
→ Deterministic QA First
→ Visual Deck Review Only When Needed
```

本 Guidance 可以作为 Stage 3 目标设计的工作基线，但在 Stage 2 Benchmark 与新 ADR 通过之前，不构成 Runtime Implementation Authority。

