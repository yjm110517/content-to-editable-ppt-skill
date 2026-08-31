# Content to Editable PPT Skill｜Visual-first 整体代码改造计划

> **目标**：在保留现有成熟 PowerPoint Builder、渲染、QA、资产处理能力的前提下，把 Skill 的上层流程改造成 Visual-first 架构。  
> **核心原则**：不推翻重写底层 PPT 构建器，而是重构 Stage 1 / Stage 2 Handoff、Layout Planner、Canonical Reconstruction Plan、Revision Patch、Visual Reviewer、Accepted Page Plan 与 Final Deck Assembly。

---

# 一、最终目标架构

```text
用户资料
   ↓
Stage 1
内容 + 大纲 + Wireframe
+ Semantic Structure
+ Chart/Table Structured Data
   ↓
用户确认
   ↓
Stage 2
宿主代理组织视觉设计
   ↓
图片生成模型
   ↓
Approved Final Design
+ Important Visual Object IDs
   ↓
用户确认
   ↓
Stage 3
Layout Planner
   ↓
Canonical Reconstruction Plan
   ↓
Deterministic Plan Compiler
   ↓
资产处理 + PPT Builder
   ↓
Structural / Editability QA
   ↓
Fresh Visual Reviewer
   │
   ├─ PASS / PASS_WITH_MINOR_DIFFERENCES
   │      ↓
   │ Accepted Page Plan
   │
   ├─ REVISION_REQUIRED
   │      ↓
   │ Revision Patch
   │      ↓
   │ Canonical Plan v2
   │
   └─ BLOCK
          ↓
      返回 Stage 1 / Stage 2

所有 Accepted Page Plans
   ↓
Shared Builder
   ↓
Final Deck
   ↓
Deck QA + Drift Check
   ↓
交付
```

---

# 二、总体改造原则

本次代码改造的本质不是：

> 重写 PowerPoint 生成器。

而是：

> 保留现有成熟的确定性 PPT Builder，把它前面的 Agent 输出从“直接维护 Runtime Artifact”改为 Canonical Reconstruction Plan，把后面的视觉审核改为 Fresh Visual Reviewer，再用 Accepted Page Plans 统一组装 Final Deck。

现有底层能力应尽量复用：

```text
PowerPoint renderer
roundtrip
asset processing
crop pipeline
font audit
shared PPT builder
contact sheet
delivery
logging
hash / evidence infrastructure
```

重点改造：

```text
Host 直接决定精确 Layout
Planner 直接输出 layout.json / crops.json / asset_manifest.json
旧 Reviewer raw-score contract
旧 review patch
Native Table 缺失
Native Chart QA 不完整
多页 direct-build orchestration
```

---

# 三、整体代码改造阶段

| 阶段 | 核心任务 | 阶段结果 |
|---|---|---|
| P1 | Canonical Reconstruction Plan 基础设施 | 新 Plan 可以驱动现有 Runtime |
| P2 | Stage 1 / Stage 2 Handoff | 上游内容、语义结构、数据与重要视觉对象真正持续保留 |
| P3 | Layout Planner 改造 | Planner 改为输出 Canonical Plan |
| P4 | PPT Builder / Native 能力补齐 | Native Chart / Table / Complex Visual 能力完整 |
| P5 | Revision Patch | 支持局部修订，不扰动已通过对象 |
| P6 | Visual Reviewer 改造 | Fresh Context + 四级审核结果 |
| P7 | Accepted Page Plan + Final Deck | 单页闭环进入最终多页 Deck |
| P8 | Skill 主流程切换 | Visual-first 成为正式主路径 |

---

# 四、P1：Canonical Reconstruction Plan + Compiler

## 4.1 目标

建立新架构与现有 Runtime 之间的兼容层：

```text
Canonical Reconstruction Plan
        ↓
Deterministic Plan Compiler
        ↓
layout.json
crops.json
asset_manifest.json
        ↓
现有 Runtime
```

这一阶段不改 Agent 主逻辑，不改现有 Builder。

---

## 4.2 建议新增

```text
schemas/
  reconstruction-plan.schema.json

scripts/
  reconstruction_plan.py
  compile_reconstruction_plan.py
```

测试：

```text
tests/
  test_reconstruction_plan.py
  test_reconstruction_plan_compiler.py
```

---

## 4.3 Canonical Plan 第一版需要表达

```text
page identity
element ids
source_ref
content_ref
data_ref
geometry
z-order
representation
style
visual relations
asset requests
provenance
```

第一版优先支持：

```text
native_text
native_shape
native_connector
raster_asset
```

暂时不强制一次做完：

```text
native_chart
native_table
revision patch
reviewer
multi-page
```

---

## 4.4 Geometry

Plan 不使用 PowerPoint 英寸作为 Agent 主要表达方式。

建议实现：

```json
{
  "geometry": {
    "coordinate_space": "normalized",
    "x": 0.08,
    "y": 0.12,
    "width": 0.36,
    "height": 0.18
  }
}
```

Compiler 负责：

```text
normalized geometry
↓
slide inches
↓
现有 layout.json
```

对于 Complex Visual：

```text
normalized source region
↓
读取 Approved Design 尺寸
↓
转换为 crops.json.box_px
```

---

## 4.5 正式文字

Canonical Plan 不重新保存正式文案。

例如：

```json
{
  "id": "title",
  "content_ref": "title",
  "representation": "native_text"
}
```

Compiler 从 Stage 1 Authority 读取真正文字。

若 `content_ref` 不存在：

```text
compile error / BLOCK
```

不得猜测或改写。

---

## 4.6 P1 完成条件

至少验证：

```text
合法 Plan → PASS
非法 geometry → FAIL
重复 element id → FAIL
未知 representation → FAIL
content_ref 正确解析
normalized geometry 正确转换
raster asset 正确生成 crop request
legacy layout/crops/manifest 校验通过
相同输入两次输出一致
现有 run_pipeline.py 可以继续构建 PPT
```

---

# 五、P2：Stage 1 / Stage 2 Handoff

## 5.1 目标

把文档中已经确定的跨阶段 Authority 真正变成 Runtime Artifact。

不允许：

```text
Stage 1
↓
生成 PNG
↓
Stage 3 只剩 PNG
```

正确结构：

```text
Semantic / Data Channel ───────────┐
                                   ├→ Stage 3
Approved Design Channel ───────────┘
```

---

## 5.2 Stage 1 需要持久化

建议具备以下逻辑 Artifact：

```text
canonical-content.json
semantic-structure.json
structured-data.json
```

需要表达：

```text
stable id
content ref
semantic role
region membership
reading order
relations
topology
Chart structured data
Table structured data
```

具体文件名后续可根据现有仓库结构调整。

---

## 5.3 Stage 2 需要持久化

逻辑上至少保留：

```text
approved-design.png
visual-objects.json
visual-spec / reconstruction hints
```

对于 Stage 2 新增的重要视觉对象：

```text
hero_illustration
product_visual_01
major_glow_01
```

必须具备稳定 ID。

微小低影响装饰不强制编号。

---

## 5.4 P2 完成条件

Stage 3 能同时读取：

```text
Stage 1 canonical content
Stage 1 semantic structure
Stage 1 structured data
Stage 2 visual objects
Approved Final Design
```

且不需要重新从图片发现正式内容和关系。

---

# 六、P3：Layout Planner 改造

## 6.1 改造目标

当前 Planner 从直接维护：

```text
layout.json
crops.json
asset_manifest.json
```

切换为只输出：

```text
Canonical Reconstruction Plan
```

---

## 6.2 主要修改范围

```text
agents/prompts/planner.md
planner-response.schema.json
prepare_agent_call.py
finalize_agent_response.py
```

实际文件名以仓库现状为准。

---

## 6.3 新 Planner 输入

```text
Stage 1 Canonical Content
Stage 1 Semantic Structure
Stage 1 Structured Data
Stage 2 Important Visual Objects
Approved Final Design
Reconstruction Policy
```

---

## 6.4 Planner 只负责两个核心任务

```text
① 已知对象 → 对齐 Approved Design 中的大体视觉位置

② 每个对象 → 决定 native / svg / raster 等重建方式
```

Planner 不再负责：

```text
PowerPoint 英寸换算
最终 pixel crop 计算
直接维护多个 Runtime JSON
重新写正式内容
重新定义 Stage 1 关系
```

---

## 6.5 输出

```text
Canonical Reconstruction Plan
```

然后：

```text
Plan
↓
Deterministic Compiler
↓
现有 Runtime
```

---

# 七、P4：Builder 与 Native 能力补齐

这一阶段不重写 Shared Builder，只补缺口。

---

## 7.1 Native Chart

目标：

```text
representation = native_chart
↓
真正 PowerPoint Chart
```

需要确认并补齐：

```text
Chart schema
Chart builder
object naming
PPTX native chart detection
structural/editability QA
```

尤其要解决：

> Builder 已支持 Chart，但 QA 也必须能正确识别它是 Native Chart。

---

## 7.2 Native Table

当前应新增正式 Table 支持：

```text
table element schema
build_table.mjs
Shared Builder table branch
native table QA
```

要求：

```text
representation = native_table
↓
PowerPoint 原生 Table
```

禁止：

```text
截图 Table
用 Shape + Text 模拟完整 Table body
```

---

## 7.3 Complex Visual Crop

保持现有 crop pipeline。

新的职责链：

```text
Layout Planner
↓
approximate source region
↓
Plan Compiler
↓
pixel crop request
↓
现有 crop runtime
↓
validated raster asset
```

Stage 3 不重新调用图片生成模型。

---

# 八、P5：Revision Patch

## 8.1 目标

把修订从“修改多个旧 Runtime Artifact”改成：

```text
Canonical Plan v1
+
Revision Patch
↓
Deterministic Apply
↓
Canonical Plan v2
```

---

## 8.2 建议新增

```text
schemas/revision-patch.schema.json

scripts/
  validate_revision_patch.py
  apply_revision_patch.py
```

---

## 8.3 Patch 必须表达

```text
base plan version
target element ids
allowed changes
linked element changes
revision reason
visual review issue reference
```

---

## 8.4 锁定规则

如果 Reviewer 只指出：

```text
chart_01
```

Patch 默认只允许修改：

```text
chart_01
```

已通过对象默认 `locked`。

只有必须联动时，才允许扩大修改范围，并记录原因。

---

## 8.5 P5 完成条件

真实验证：

```text
一个对象失败
↓
Patch
↓
只改变该对象或必要局部分组
↓
其他对象保持不变
```

---

# 九、P6：Visual Reviewer 改造

## 9.1 目标

从旧 Reviewer：

```text
source image
vs
render
→ raw scores
```

切换为：

```text
Approved Design
+
Current Render
+
Deterministic Review Context
+
QA Evidence
↓
Fresh Visual Reviewer
```

---

## 9.2 新增 Reviewer Context Compiler

建议新增：

```text
build_review_context.py
```

它不是 Agent，不调用 LLM。

输入：

```text
Stage 1 Authority
Stage 2 Visual Objects
Canonical Plan
QA Evidence
```

输出：

```text
review-context.json
```

只做确定性字段投影。

---

## 9.3 Reviewer 输出

固定为：

```text
PASS
PASS_WITH_MINOR_DIFFERENCES
REVISION_REQUIRED
BLOCK
```

如果：

```text
REVISION_REQUIRED
```

必须尽量返回：

```text
affected object ids
issue type
description
revision direction
```

但不得输出：

```text
新 geometry
新 crop box
新 Reconstruction Plan
```

---

## 9.4 Fresh Context

Reviewer 不继承 Planner Chat History。

不得由 Host Agent 或 Planner 自由总结审核上下文。

---

# 十、P7：Accepted Page Plan + Final Deck

## 10.1 Accepted Page Plan

一页通过：

```text
Structural / Editability QA
+
Visual Review
```

后冻结：

```text
Accepted Page Plan
```

至少绑定：

```text
Canonical Plan version
validated assets
accepted render
QA evidence
visual review evidence
provenance / hashes
```

---

## 10.2 Asset Immutability

Final Deck 必须复用 Reviewer 已审核的同一份资产。

禁止：

```text
单页审核时 crop A
↓
Final Deck 又重新 crop B
```

---

## 10.3 Final Deck Assembly

```text
Accepted Page Plan 1
Accepted Page Plan 2
...
Accepted Page Plan N
↓
Shared Builder
↓
一个 Presentation
↓
Final Deck.pptx
```

不要采用：

```text
per-slide PPTX
↓
COM Merge
```

作为正式路径。

---

## 10.4 Final Deck QA

默认进行：

```text
页数
结构完整性
Native Chart/Table
字体
资产
Accepted Render vs Final Render Drift
```

不默认再次运行 Whole-Deck Visual Reviewer。

只有：

```text
drift
risk warning
unexpected shared-build change
```

才定向触发视觉复核。

---

# 十一、P8：Skill 主流程切换

最后才修改正式 Skill 入口。

目标：

```text
Stage 1
↓
用户确认
↓
Stage 2
↓
用户确认视觉
↓
Stage 3 Page Reconstruction
↓
Accepted Page Plans
↓
Final Deck
```

---

## 11.1 SKILL.md

最终需要同步：

```text
Stage 1 authority
Stage 2 approved design
Stage 3 orchestration
Layout Planner
Visual Reviewer
Accepted Page Plan
Final Deck
```

不再要求 Host Agent 直接负责最终精确英寸坐标。

---

## 11.2 run.py / 主 Orchestrator

不建议第一时间删除现有 `run.py`。

可以逐步：

```text
保留 legacy direct-build route
+
增加 Visual-first route
↓
真实测试稳定
↓
再决定是否收缩旧路径
```

---

# 十二、测试体系

测试应随每个阶段同步增加，不要最后统一补。

整体测试层次：

```text
Contract Tests
↓
Compiler Tests
↓
Builder Tests
↓
QA Tests
↓
Agent Fixture Tests
↓
Single-page E2E
↓
Multi-page E2E
```

---

## 12.1 代表性真实场景

至少保留：

```text
B01 纯文字
B02 卡片
B03 图文
B04 流程
B05 Chart
B06 Table
B07 Complex Visual
B08 Revision Patch
```

---

## 12.2 每阶段 Gate

每个 P 阶段都需要：

```text
当前阶段新增测试 PASS
+
既有重要测试 PASS
+
真实样例 Smoke PASS
+
没有无关回归
```

再进入下一阶段。

---

# 十三、现有代码保留 / 改造边界

## 13.1 尽量保留

```text
PowerPoint renderer
roundtrip
asset processing
crop pipeline
font audit
shared PPT builder
contact sheet
delivery
logging
hash / evidence infrastructure
```

---

## 13.2 重点替换

```text
Host 直接决定精确 Layout
Planner 直接输出三个 Runtime Artifact
旧 Visual Reviewer raw-score contract
旧 review patch
Native Table 缺失
Native Chart QA 不完整
多页 direct-build orchestration
```

---

# 十四、最终代码结构示意

> 以下仅表示职责，不要求机械创建所有目录。

```text
content-to-editable-ppt/
│
├─ SKILL.md
│
├─ agents/
│  └─ prompts/
│     ├─ planner.md
│     └─ visual_reviewer.md
│
├─ schemas/
│  ├─ stage1-*.schema.json
│  ├─ stage2-visual-objects.schema.json
│  ├─ reconstruction-plan.schema.json
│  ├─ revision-patch.schema.json
│  ├─ review-context.schema.json
│  ├─ reviewer-response.schema.json
│  └─ accepted-page-plan.schema.json
│
├─ scripts/
│  ├─ compile_reconstruction_plan.py
│  ├─ apply_revision_patch.py
│  ├─ build_review_context.py
│  ├─ assemble_final_deck.py
│  │
│  ├─ existing crop/render/QA/runtime...
│  │
│  └─ shared/ppt/
│     ├─ build_text.mjs
│     ├─ build_shape.mjs
│     ├─ build_line.mjs
│     ├─ build_image.mjs
│     ├─ build_chart.mjs
│     ├─ build_table.mjs
│     └─ build_slide_into_presentation.mjs
│
└─ tests/
   ├─ contracts/
   ├─ compiler/
   ├─ reviewer/
   ├─ runtime/
   └─ e2e/
```

---

# 十五、最终开发顺序

严格按照：

```text
P1 Canonical Plan + Compiler
↓
P2 Stage 1 / Stage 2 Handoff
↓
P3 Layout Planner
↓
P4 Native Chart / Table / Asset Build
↓
P5 Revision Patch
↓
P6 Fresh Visual Reviewer
↓
P7 Accepted Page Plan + Final Deck
↓
P8 Skill 主流程切换
↓
完整真实场景验证
↓
删除或收缩旧兼容路径
```

---

# 十六、最终判断

这次 Visual-first 改造不需要推翻整个项目。

真正需要做的是：

> **保留底层成熟 Runtime，把 Stage 1 → Stage 2 → Stage 3 的权威数据流重新接好；让 Layout Planner 输出 Canonical Reconstruction Plan；由确定性 Compiler 驱动现有 Builder；再用 Revision Patch、Fresh Visual Reviewer 和 Accepted Page Plan 完成单页闭环与最终 Deck 装配。**

这条路线能够：

- 最大限度复用现有代码；
- 避免一次性重写造成大面积回归；
- 保持 Agent 与 Runtime 解耦；
- 让 Chart / Table / Complex Visual 有明确重建政策；
- 支持真正的局部修订；
- 保证 Final Deck 使用审核过的同一份资产与页面计划。

