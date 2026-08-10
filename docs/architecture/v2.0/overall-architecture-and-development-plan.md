# Content to Editable PPT Skill 总体架构与开发计划 v2.0

> 英文名：Content to Editable PPT Skill Architecture & Development Plan v2.0

## 1. 文档目的

本文档定义 `Content to Editable PPT Skill` v2.0 的总体架构、模块边界、运行层级、目录组织建议、现有能力复用策略、Windows Runtime 方案、Agent 体系、Content-to-PPT 上游能力、Single-Slide Runtime 强化方案、多页编排、Deck Assembly、测试顺序和阶段性开发计划。

本文档是以下已冻结规范的架构级汇总与实施蓝图：

- 《需求规格说明 v1.1》
- 《功能规格说明 v1.1》
- 《非功能需求与质量指标 v1.1》
- 《Agent 职责与交接契约 v1.1》
- 《运行环境安装与引导规范 v1.0》
- 《单页 Runtime 执行与错误恢复规范 v1.0》
- 《产物、状态与权威数据契约 v1.0》

本文档不重新定义上述规范已经冻结的业务规则，而是回答：

> 现有 GitHub 项目应该如何在不推翻 Single-Slide Runtime 的前提下，演进成一个面向 Claude Code、Codex 的完整 Content-to-Editable-PPT Skill。

---

# 2. v2.0 核心架构决策

v2.0 正式冻结以下架构原则。

## 2.1 增量演进，不重写现有 Single-Slide Runtime

现有 Image-to-Editable-PPT Runtime 继续作为核心底座。

v2.0 采用：

```text
Existing Single-Slide Runtime
        ↑
修复、增强、稳定
        ↑
新增 Content-to-PPT 上游
        +
新增 Deck Orchestration 下游
```

不采用：

```text
删除现有 Runtime
→ 从头重写 Planner / Builder / Reviewer
```

现有经过验证的：

- Layout Planner；
- Visual Reviewer；
- Asset Processing；
- PPT Build；
- PowerPoint Render；
- Structural QA；
- OOXML / Font Audit；

均优先保留和复用。

## 2.2 第一阶段仅正式支持 Windows

v2.0 第一阶段平台范围：

```text
Windows only
```

正式参考环境：

```text
Windows
+
Microsoft PowerPoint
+
PowerPoint COM
```

第一阶段不实现、不测试、不承诺：

- macOS；
- Linux；
- LibreOffice Backend；
- macOS PowerPoint Automation；
- 跨平台一致渲染；
- Compatible Backend。

架构可以保留未来扩展点，但不得让跨平台工作阻塞 v2.0 MVP。

## 2.3 Host Agent 不新增一个额外产品

Host Agent 即：

- Claude Code；
- Codex；
- 后续兼容的宿主 Coding Agent。

Skill 不再创建一个重复的“Host Agent 子进程”。

Host 负责：

- 任务路由；
- 材料理解；
- Outline；
- 用户确认；
- Wireframe；
- Visual Design；
- 生图调度；
- 多页编排；
- Issue Routing；
- Delivery Gate。

## 2.4 Specialist Agent 仅保留两个

正式保留：

```text
Layout Planner
Visual Reviewer
```

不新增：

- Outline Planner；
- Wireframe Planner；
- Visual Designer Agent；
- Runtime Agent；
- Deck Reviewer；
- Revision Agent。

原则：

> 有功能不等于必须有 Agent。

## 2.5 薄 SKILL.md + references 模块化

`SKILL.md` 负责：

- Skill 定位；
- 入口识别；
- 总流程；
- 核心禁止事项；
- 阶段路由；
- 何时加载哪个 reference。

详细规则拆分到 `references/`。

避免：

```text
一个超长 SKILL.md
→ 每次加载所有规则
```

## 2.6 Wireframe 由 Host 规划，确定性 Renderer 绘制

Host 输出：

```text
Wireframe Spec
```

确定性 Runtime 输出：

```text
SVG
```

必要时：

```text
SVG → PNG
```

SVG 作为第一版 Wireframe Preview 的主要格式。

## 2.7 Design Image 由 Host 调宿主可用生图能力

不建立 Visual Designer Agent。

流程：

```text
Approved Slide Content
+
Wireframe
+
Deck Visual Direction
+
User Constraints
↓
Host Visual Design Brief
↓
Available Image Generation Capability
↓
Design Image
```

Skill 规定：

- 输入；
- 视觉规则；
- 输出；
- 页面一致性要求；

但不在 v2.0 中绑定一个固定图像模型 Adapter。

## 2.8 多页采用有限并行

每页是独立任务单元。

允许：

```text
Slide 01
Slide 02
Slide 03
...
```

有限并发执行。

并发数配置化，不在规范中写死。

禁止无限并发。

## 2.9 Deck Assembly 第一版使用 PowerPoint COM

第一版采用：

```text
Per-slide PPTX
↓
PowerPoint COM
↓
Final Deck PPTX
```

不在 MVP 中实现复杂 OOXML Merge。

## 2.10 保留 Image-to-Editable-PPT 独立入口

v2.0 仍然正式支持：

```text
User Image
↓
Source Slide Content
↓
Layout Planner
↓
Single-Slide Runtime
↓
Editable PPT
```

不得强迫用户经过：

- Outline；
- Wireframe；
- Visual Design。

---

# 3. v2.0 产品形态

`Content to Editable PPT Skill` 不是：

- 独立桌面软件；
- Web SaaS；
- 前后端系统；
- 云任务平台；
- 独立账号系统；
- 数据库产品。

它是：

> 被 Claude Code、Codex 等 AI Coding Agent 调用和执行的 Skill。

其主要职责是为宿主 Agent 提供：

```text
Rules
+
Specialist Agents
+
Schemas
+
Deterministic Runtime
+
Windows PowerPoint Automation
+
State / Artifacts
```

---

# 4. 两条正式入口

## 4.1 Content-to-PPT

用户提供：

- 文本；
- Word；
- PDF；
- 资料；
- PPT 要求；
- 视觉要求。

流程：

```text
User Materials
↓
Host Material Understanding
↓
Candidate Outline
↓
User Confirmation
↓
Approved Outline
↓
Approved Slide Content
↓
Host Wireframe Planning
↓
Wireframe Renderer
↓
Host Visual Design
↓
Design Images
↓
Single-Slide Runtime
↓
Per-slide Editable PPT
↓
Deck Assembly
↓
Final Editable PPTX
```

## 4.2 Image-to-Editable-PPT

用户直接提供：

- PPT Screenshot；
- 设计图；
- 页面图片。

流程：

```text
User Image
↓
Host / Vision
↓
Source Slide Content
↓
Freeze
↓
Single-Slide Runtime
↓
Editable PPT
```

不进入 Outline / Wireframe / Visual Design 阶段。

---

# 5. 总体逻辑架构

v2.0 采用五层架构。

```text
┌────────────────────────────────────────────────┐
│ Layer 1 — Host / Skill Rules                   │
│ Intent Routing                                 │
│ Material Understanding                         │
│ Outline Planning                               │
│ User Confirmation                              │
│ Wireframe Planning                             │
│ Visual Design                                  │
│ Orchestration                                  │
│ Delivery Gate                                  │
├────────────────────────────────────────────────┤
│ Layer 2 — Specialist Agents                    │
│ Layout Planner                                 │
│ Visual Reviewer                                │
├────────────────────────────────────────────────┤
│ Layer 3 — Single-Slide Runtime                 │
│ Validation                                     │
│ Asset Processing                               │
│ Build                                          │
│ Audit                                          │
│ PowerPoint Render                              │
│ Structural QA                                  │
│ Patch / Resume                                 │
├────────────────────────────────────────────────┤
│ Layer 4 — Deck Runtime                         │
│ Slide Scheduling                               │
│ Limited Parallelism                            │
│ Deck State                                     │
│ PowerPoint COM Assembly                        │
│ Deck QA                                        │
├────────────────────────────────────────────────┤
│ Layer 5 — Managed Windows Runtime              │
│ Install                                        │
│ Bootstrap                                      │
│ Verify                                         │
│ Fast Preflight                                 │
│ Repair                                         │
│ PowerPoint COM                                 │
└────────────────────────────────────────────────┘
```

---

# 6. Layer 1：Host / Skill Rules

## 6.1 Host 角色

Host 即当前执行 Skill 的：

```text
Claude Code
或
Codex
```

Host 是整个 Workflow Orchestrator。

## 6.2 Host 负责

### Task Routing

判断：

```text
Content-to-PPT
or
Image-to-Editable-PPT
```

### Material Understanding

读取用户材料并建立页面内容候选。

### Outline Planning

生成：

```text
Candidate Outline
```

### User Confirmation

Outline 为强制确认点。

确认后形成：

```text
Approved Outline
```

### Approved Slide Content

从 Approved Outline 形成每页正式内容。

### Wireframe Planning

为每页形成：

```text
Wireframe Spec
```

### Visual Design

结合：

- 内容；
- Wireframe；
- 用户视觉要求；
- Deck Style；

形成 Visual Design Brief。

### Image Generation

调用宿主可用图片生成能力生成：

```text
Design Image
```

### Orchestration

控制：

- 页面调度；
- Runtime 调用；
- Agent 调用；
- Reviewer Issue Routing；
- Targeted Revision；
- Deck Assembly。

### Delivery Gate

根据：

- Structural QA；
- Visual Reviewer；
- Content Accuracy；
- Editability；
- Warning；

产生最终状态。

---

# 7. Layer 2：Specialist Agents

## 7.1 Layout Planner

现有：

```text
agents/planner.yaml
```

继续复用。

主要职责：

```text
Design Image
+
Approved / Source Slide Content
+
Assets
+
Editability Rules
↓
Reconstruction Spec
```

并支持：

```text
Targeted Patch
```

不得负责：

- Outline；
- Wireframe；
- Visual Design；
- Runtime 安装；
- Build；
- 最终审核；
- Delivery。

## 7.2 Visual Reviewer

现有：

```text
agents/visual_reviewer.yaml
```

继续复用。

输入：

```text
Design Image
+
Actual PPT Render
+
Approved Content Summary
+
Structural QA Summary
+
Compact Element Index
+
Rubric
```

输出：

```text
pass
revise
critical
technical_failure
```

Reviewer 使用独立上下文。

---

# 8. Layer 3：Single-Slide Runtime

该层基于现有 Runtime 增量增强。

标准流程：

```text
Runtime Ready
↓
Layout Planner
↓
Shared Validation
↓
Asset Processing
↓
Build
↓
Font / OOXML Audit
↓
PowerPoint Render
↓
Structural QA
↓
Visual Reviewer
↓
Targeted Patch
↓
Delivery Gate
```

v2.0 的重点不是重写该层，而是解决：

- 环境问题晚发现；
- Planner 重复调用；
- Validator 不一致；
- 局部问题全量 Replan；
- Reviewer 超时无法退出；
- 无 Resume；
- 无 Cache；
- 无 Zero-Asset Fast Path；
- 状态和错误分类不清晰。

---

# 9. Shared Validator

v2.0 必须建立统一 Validation 层。

避免：

```text
Planner Candidate Validator
≠
Builder / Finalizer Validator
```

统一覆盖：

```text
Schema
Semantic Rules
Cross-element Rules
Path Rules
```

Layout Planner 的 Initial Spec 与 Targeted Patch 都必须通过同一 Validation Contract。

---

# 10. Targeted Patch 架构

局部问题不得默认 Full Replan。

标准路径：

```text
Reviewer / QA Issue
↓
Host Classification
↓
Layout Planner Targeted Patch
↓
Shared Validator
↓
Only Affected Stages Rerun
```

例如：

```text
connector endpoint
→ Patch
→ Build
→ Render
→ QA
→ Reviewer
```

而不是：

```text
connector错误
→ Full Planner
→ 全资产
→ 全Build
```

---

# 11. Stage Reuse 与 Resume

Single-Slide Runtime 必须支持：

```text
Passed Stage
+
Input Unchanged
=
Reuse
```

例如：

```text
Planner pass
Assets pass
Build pass
Render fail
```

恢复：

```text
Resume from Render
```

不重新执行：

- Planner；
- Assets；
- Build。

Stage Reuse 为 v2.0 Runtime Hardening 的核心能力。

---

# 12. Layer 4：Deck Runtime

## 12.1 Deck Orchestrator

Deck Runtime 负责：

- 建立 slide task；
- 页面顺序；
- 页面 workspace；
- 页面状态汇总；
- 有限并发；
- 单页失败隔离；
- Deck Assembly；
- Deck QA。

## 12.2 单页隔离

每页拥有独立：

```text
run_state
Reconstruction Spec
Assets
PPTX
Render
QA
Reviewer Result
Patch
```

## 12.3 有限并行

设计：

```text
Deck
├─ Slide Task 01
├─ Slide Task 02
├─ Slide Task 03
└─ ...
```

由可配置 Scheduler 控制并发数量。

例如概念配置：

```text
max_parallel_slides
```

具体默认值在性能测试后确定。

## 12.4 PowerPoint COM 并发边界

虽然页面任务可以并行，但 PowerPoint COM 是否允许真正多实例并行必须通过实验验证。

因此第一版允许：

```text
Planner / Asset / Validation
→ 并行
```

而 PowerPoint COM：

```text
Render / Assembly
```

可以在实现中使用：

- 串行队列；
- 有限锁；
- 单 Office Worker；

以实际稳定性测试结果为准。

---

# 13. Deck Assembly

第一版：

```text
slide-01.pptx
slide-02.pptx
slide-03.pptx
...
↓
PowerPoint COM
↓
final-deck.pptx
```

Deck Assembly 必须保证：

- 页面顺序正确；
- 页面数量正确；
- 页面内容保持；
- 页面对象仍可编辑；
- 文件能由 PowerPoint 正常打开；
- 不出现丢图；
- 不出现页面空白；
- 不破坏字体和媒体关系。

第一版不采用复杂 OOXML Merge 作为主要方案。

---

# 14. Deck QA

第一版 Deck QA 采用确定性检查，不新增 Deck Reviewer Agent。

至少检查：

- slide count；
- slide order；
- final PPTX 可打开；
- 每页存在；
- 页面没有意外重复；
- 页面没有意外丢失；
- 页面尺寸一致；
- 关键 shared assets 存在；
- 最终文件可保存；
- 已交付页面状态与 Deck State 一致。

视觉质量继续以单页 Reviewer 为主。

---

# 15. Layer 5：Managed Windows Runtime

v2.0 第一阶段仅支持：

```text
Windows
+
Microsoft PowerPoint
```

## 15.1 Installation

主要入口：

```text
install.ps1
```

## 15.2 Bootstrap

负责：

- 检测 Windows；
- 检测架构；
- 准备受控 Python Runtime；
- 准备 Python 依赖；
- 准备 Node 依赖；
- 检测 PowerPoint；
- 检测 COM；
- Smoke Test；
- Runtime Manifest。

## 15.3 Fast Preflight

任务开始前：

```text
Fast Preflight
```

必须在 Layout Planner 前通过。

## 15.4 Repair

可修复环境问题：

```text
Preflight Fail
↓
Runtime Repair
↓
Reverify
↓
Resume
```

不能触发 Planner。

---

# 16. Runtime Backend 第一版策略

虽然长期可以抽象：

```text
Office Backend
```

但 v2.0 第一阶段实际只实现：

```text
PowerPoint Backend
```

不开发：

```text
LibreOffice Backend
macOS Backend
```

为了未来可扩展，内部调用可以尽量通过稳定接口封装，例如概念上：

```text
render_pptx()
open_validate()
assemble_deck()
```

但不得为“未来可能的跨平台”过度设计当前 MVP。

---

# 17. Wireframe 子系统

## 17.1 Host 输出

```text
Wireframe Spec
```

至少描述：

- page id；
- page size；
- title region；
- content blocks；
- image zones；
- chart / diagram zones；
- relative positions；
- hierarchy；
- visual emphasis。

## 17.2 Deterministic Renderer

建议新增：

```text
scripts/render_wireframe.py
```

输出：

```text
wireframe.svg
```

必要时：

```text
wireframe.png
```

Wireframe Preview 不是最终设计图。

---

# 18. Visual Design 子系统

## 18.1 Host 生成 Design Brief

输入：

```text
Approved Slide Content
Wireframe Spec
User Visual Constraints
Deck Visual Direction
```

输出：

```text
Visual Design Brief
```

## 18.2 图片生成

Host 调宿主图像生成能力。

输出：

```text
Design Image
```

## 18.3 权威性

```text
Design Image
= Visual Source of Truth
```

但：

```text
Approved Slide Content
= Text Source of Truth
```

Design Image OCR 不能覆盖正式文字。

---

# 19. 页面设计确认策略

## 19.1 ≤ 5 页

默认：

```text
Approved Outline
↓
All Wireframes
↓
All Design Images
```

不额外强制 Sample Confirmation。

## 19.2 > 5 页

默认：

```text
Approved Outline
↓
Representative Sample
↓
必要时用户确认
↓
Full Design Images
```

Representative Sample 建议覆盖：

- 封面；
- 典型正文页；
- 复杂视觉页。

## 19.3 用户覆盖

上述 5 页规则只是：

```text
default orchestration heuristic
```

不是不可变流程。

用户可以要求：

- 4 页先看 Sample；
- 20 页直接全部生成。

用户要求优先。

---

# 20. Backward Compatibility

v2.0 必须保持 Image-to-Editable-PPT 的已有价值。

## 20.1 单页入口继续有效

用户：

```text
把这张图片转成可编辑PPT
```

仍然直接进入：

```text
Image
↓
Source Slide Content
↓
Single-Slide Runtime
```

## 20.2 现有单页数据结构尽量保持兼容

现有单页：

```text
request.json
run_state.json
```

尽量保持兼容。

Deck 层新增：

```text
deck_request
deck_state
```

位于 Single-Slide Runtime 上方。

## 20.3 不强制旧任务迁移到 Deck 模型

单页任务不需要为了架构统一而人为创建完整 Deck 工作流。

---

# 21. Artifact 与 State 架构

## 21.1 单页

```text
run_state
```

是单页任务状态权威。

## 21.2 Deck

```text
deck_state
```

仅负责：

- 页面列表；
- 页面顺序；
- 每页总体状态；
- Assembly；
- Deck QA；
- Final Delivery。

## 21.3 Runtime

```text
runtime-manifest
```

负责环境状态。

正式分离：

```text
runtime-manifest
≠
run_state
≠
deck_state
```

---

# 22. 建议项目目录结构

v2.0 目标目录建议：

```text
content-to-editable-ppt/
│
├─ SKILL.md
│
├─ agents/
│   ├─ openai.yaml
│   ├─ planner.yaml
│   ├─ visual_reviewer.yaml
│   └─ prompts/
│
├─ references/
│   ├─ content-planning.md
│   ├─ outline-contract.md
│   ├─ wireframe-planning.md
│   ├─ visual-design.md
│   ├─ reconstruction-rules.md
│   ├─ runtime-recovery.md
│   ├─ artifact-authority.md
│   └─ delivery-gate.md
│
├─ schemas/
│   ├─ deck_request.schema.json
│   ├─ approved_outline.schema.json
│   ├─ slide_content.schema.json
│   ├─ wireframe_spec.schema.json
│   ├─ reconstruction_spec.schema.json
│   ├─ reviewer_result.schema.json
│   ├─ patch.schema.json
│   ├─ run_state.schema.json
│   ├─ deck_state.schema.json
│   └─ runtime_manifest.schema.json
│
├─ scripts/
│   ├─ bootstrap_runtime.py
│   ├─ verify_install.py
│   ├─ environment_preflight.py
│   ├─ repair_runtime.py
│   ├─ render_wireframe.py
│   ├─ validate_reconstruction.py
│   ├─ process_assets.py
│   ├─ build_slide.py
│   ├─ render_powerpoint.py
│   ├─ structural_qa.py
│   ├─ apply_patch.py
│   ├─ assemble_deck.py
│   └─ deck_qa.py
│
├─ runtime/
│   ├─ dependency-locks/
│   └─ manifest/
│
├─ examples/
│
├─ tests/
│
├─ install.ps1
│
└─ README.md
```

说明：

> 上述文件名是目标模块建议，不代表必须一次性完全按此命名重构。

原则是保留现有可用脚本，并逐步移动到清晰责任边界。

---

# 23. SKILL.md 目标结构

`SKILL.md` 不应成为全部实现细节的存放地。

建议结构：

```text
1. Skill Purpose
2. Supported Platform
3. Task Routing
4. Core Workflow
5. Content Freeze Rules
6. Agent Routing
7. Runtime Readiness Gate
8. Visual Revision Rules
9. Delivery Rules
10. Reference Loading Map
```

详细规则放入 `references/`。

---

# 24. references/ 目标职责

## content-planning.md

负责：

- 材料理解；
- 内容整理；
- 大纲形成前的允许与禁止。

## outline-contract.md

负责：

- Outline 字段；
- 用户确认；
- Approved Outline；
- 内容冻结。

## wireframe-planning.md

负责：

- 页面分区；
- 布局规划；
- Wireframe Spec。

## visual-design.md

负责：

- Visual Design Brief；
- Deck Style；
- Design Image 生成规则；
- Sample Strategy。

## reconstruction-rules.md

负责：

- 可编辑性；
- native / raster；
- Layout Planner 约束。

## runtime-recovery.md

负责：

- Technical Retry；
- Targeted Patch；
- Resume；
- Stage Reuse；
- Error Classification。

## artifact-authority.md

负责：

- Source of Truth；
- Artifact invalidation；
- State 分离。

## delivery-gate.md

负责：

- delivered；
- delivered_with_warnings；
- revision_required；
- failed。

---

# 25. Agent 文件策略

第一版继续使用现有：

```text
agents/planner.yaml
agents/visual_reviewer.yaml
```

如果需要更新：

- 输入字段；
- Patch Mode；
- Reviewer compact context；
- schema；

应在原 Agent 上演进。

禁止通过新增：

```text
planner_v2.yaml
planner_new.yaml
planner_final.yaml
```

长期形成多个并行权威版本。

---

# 26. 数据流

Content-to-PPT 数据流：

```text
User Materials
↓
Deck Request
↓
Candidate Outline
↓
Approved Outline
↓
Approved Slide Content
↓
Wireframe Spec
↓
Wireframe Preview
↓
Visual Design Brief
↓
Design Image
↓
Reconstruction Spec
↓
Processed Assets
↓
PPTX
↓
Render
↓
Structural QA
↓
Reviewer Result
↓
Patch（可选）
↓
Per-slide Delivered Result
↓
Deck Assembly
↓
Deck QA
↓
Final PPTX
```

---

# 27. Source-of-Truth 架构

正式保持：

```text
Approved Outline
= Deck 内容结构权威
```

```text
Approved Slide Content
= Content-to-PPT 页面文字权威
```

```text
Source Slide Content
= Image-to-Editable-PPT 页面文字权威
```

```text
Design Image
= 页面视觉权威
```

```text
PPTX / Render
= 实际结果
```

任何模块不得破坏此关系。

---

# 28. 错误恢复架构

错误分类：

```text
Environment
Technical
Specification
Content
Visual
Unrecoverable
```

对应：

```text
Environment
→ Runtime Repair

Technical
→ Technical Retry

Local Specification
→ Targeted Patch

Global Semantic
→ Limited Full Replan

Content
→ Host / User Confirmation

Visual
→ Targeted Patch / Visual Design

Unrecoverable
→ Failed
```

禁止：

```text
任何错误
→ 全量重新Planner
```

---

# 29. 性能优化架构

v2.0 不设固定总耗时 SLA。

性能目标：

> 减少没有质量收益的重复执行。

重点实现：

- Fast Preflight；
- Zero-Asset Fast Path；
- Shared Validator；
- Stage Cache；
- Resume；
- Targeted Patch；
- Limited Parallelism；
- Reviewer Compact Context；
- Reviewer timeout degradation。

主要优化对象是：

```text
无效 Planner Call
无意义重建
重复 Asset Processing
重复 Build
重复 Render
无退出 Reviewer Waiting
```

而不是减少必要审核。

---

# 30. v2.0 开发阶段总览

开发采用：

```text
P0
Baseline Freeze

P0.5
Single-Slide Runtime Hardening

P1
Host Content Planning

P2
Wireframe

P3
Visual Design

P4
Deck Orchestration

P5
Deck Assembly & QA

P6
Regression / Docs / Release
```

---

# 31. P0 — Baseline Freeze

## 31.1 目标

在修改前冻结当前 Image-to-Editable-PPT Runtime 的可比较基线。

## 31.2 工作

- 选择当前稳定示例；
- 记录输入；
- 保存 Planner 输出；
- 保存 PPTX；
- 保存 Render；
- 保存 QA；
- 保存 Reviewer 状态；
- 记录耗时；
- 记录当前 Agent 调用次数；
- 记录已知问题。

## 31.3 输出

```text
baseline/
```

至少包含：

- sample inputs；
- expected artifacts；
- timing；
- current failures；
- baseline report。

## 31.4 Gate

P0 完成后才能进入 Runtime Hardening。

目的：

> 后续任何重构都可以证明没有破坏原有核心能力。

---

# 32. P0.5 — Single-Slide Runtime Hardening

这是 v2.0 最重要的底层阶段。

在新增 Content-to-PPT 之前先完成。

## 32.1 Managed Runtime

实现：

```text
install.ps1
bootstrap_runtime
verify_install
fast_preflight
runtime_repair
```

## 32.2 Shared Validation

统一：

- Planner Candidate；
- Patch；
- Builder input；
- Final validation。

## 32.3 Error Classification

实现：

```text
environment
technical
local spec
global semantic
content
visual
unrecoverable
```

## 32.4 Technical Retry

技术失败不调用 Planner。

## 32.5 Targeted Patch

Planner 支持局部 Patch。

## 32.6 Resume

从失败阶段继续。

## 32.7 Stage Reuse

输入未变化的通过阶段可复用。

## 32.8 Zero-Asset Fast Path

无资产页面不执行无意义 asset pipeline。

## 32.9 Reviewer Degradation

Reviewer timeout / unavailable：

```text
QA pass
→ delivered_with_warnings
```

不得触发 Replan。

## 32.10 Gate

P0.5 必须通过单页回归测试后，才能作为 Content-to-PPT 的底座。

---

# 33. P1 — Host Content Planning

## 33.1 目标

新增内容型 PPT 入口。

## 33.2 新增能力

- task routing；
- deck request；
- material understanding；
- candidate outline；
- user confirmation；
- approved outline；
- approved slide content。

## 33.3 不新增 Outline Planner Agent

全部由 Host 按 reference 规则执行。

## 33.4 Gate

必须验证：

- 用户能够修改 Outline；
- 用户确认后内容冻结；
- 下游不能改写；
- Image-to-Editable-PPT 不被强制进入 P1。

---

# 34. P2 — Wireframe

## 34.1 新增能力

```text
Approved Slide Content
↓
Host Wireframe Planning
↓
Wireframe Spec
↓
SVG Renderer
```

## 34.2 新增模块

- wireframe planning reference；
- wireframe schema；
- deterministic SVG renderer。

## 34.3 Gate

至少验证：

- 页面分区完整；
- 内容不会因 Wireframe 被改写；
- SVG 能稳定渲染；
- 用户可以选择是否查看 Wireframe。

---

# 35. P3 — Visual Design

## 35.1 新增能力

- Visual Design Brief；
- Deck visual direction；
- image generation contract；
- ≤5 / >5 page strategy；
- Design Image artifact。

## 35.2 不新增 Visual Designer Agent

由 Host 调现有图片生成能力。

## 35.3 Gate

验证：

- Design Image 与 Approved Slide Content 对齐；
- Design Image 可以作为 Layout Planner 输入；
- 用户视觉要求得到优先执行；
- Sample Strategy 可被用户覆盖。

---

# 36. P4 — Deck Orchestration

## 36.1 目标

把：

```text
Design Images
```

稳定接入：

```text
Single-Slide Runtime
```

## 36.2 新增能力

- slide workspace；
- slide task；
- run_state isolation；
- deck_state；
- limited parallel scheduler；
- issue routing；
- per-slide delivery status。

## 36.3 Gate

验证：

- 单页失败不污染其他页；
- 页面顺序不乱；
- 页面资产隔离；
- Reviewer issue 不串页；
- Patch 不串页；
- 并行执行结果与串行结果一致。

---

# 37. P5 — Deck Assembly & Deck QA

## 37.1 Assembly

实现：

```text
PowerPoint COM Assembly
```

## 37.2 Deck QA

检查：

- slide count；
- slide order；
- file openability；
- page integrity；
- page dimensions；
- no blank pages；
- no lost slides；
- basic editable objects retained。

## 37.3 Gate

Final Deck 必须由 Microsoft PowerPoint：

- 正常打开；
- 正常保存；
- 正常播放 / 浏览；
- 页面顺序正确。

---

# 38. P6 — Regression / Docs / Release

## 38.1 Regression

必须验证：

```text
Image-to-Editable-PPT
```

没有退化。

## 38.2 Claude Code

完成正式使用测试。

## 38.3 Codex

完成正式使用测试。

## 38.4 Installation

验证干净 Windows 环境：

```text
install.ps1
→ Bootstrap
→ Verify
→ Task
```

## 38.5 Documentation

更新：

- README；
- SKILL.md；
- examples；
- installation；
- troubleshooting；
- architecture notes。

## 38.6 Release Gate

P6 通过后才能作为 v2.0 正式 Release Candidate。

---

# 39. P0–P6 依赖关系

```text
P0
↓
P0.5
↓
P1
↓
P2
↓
P3
↓
P4
↓
P5
↓
P6
```

其中：

> P0.5 是整个 v2.0 的关键技术底座。

不建议：

```text
Single-Slide Runtime仍不稳定
↓
直接开发10页并行Content-to-PPT
```

否则会放大现有问题。

---

# 40. 建议开发分支策略

建议每个阶段使用独立 feature branch，例如概念上：

```text
v2/runtime-hardening
v2/content-planning
v2/wireframe
v2/visual-design
v2/deck-orchestration
v2/deck-assembly
```

每阶段：

```text
implementation
↓
tests
↓
baseline regression
↓
merge
```

具体 Git 策略可根据项目现有习惯调整。

---

# 41. Schema 开发顺序

建议按依赖顺序：

```text
runtime_manifest
↓
run_state
↓
reconstruction_spec / patch
↓
deck_request
↓
approved_outline
↓
slide_content
↓
wireframe_spec
↓
reviewer_result
↓
deck_state
```

已有 Schema 应优先扩展而不是重复新建。

---

# 42. Runtime 脚本开发顺序

建议：

```text
environment_preflight
↓
shared_validator
↓
technical_retry wrapper
↓
resume / stage cache
↓
targeted patch
↓
wireframe renderer
↓
deck orchestrator
↓
assemble_deck
↓
deck_qa
```

避免先开发 Deck，再回头补单页恢复机制。

---

# 43. Reviewer 优化顺序

第一版 Reviewer 改造优先：

1. compact input；
2. independent context；
3. normalized issue schema；
4. target element ids；
5. reviewer timeout；
6. technical failure classification；
7. warning delivery；
8. no planner retry on timeout。

不需要在 v2.0 初期追求复杂 Reviewer 多 Agent 体系。

---

# 44. Layout Planner 优化顺序

优先：

1. 生产级 Shared Validator；
2. Initial / Patch 双模式；
3. restricted patch paths；
4. element ids 稳定；
5. connector validation；
6. asset references；
7. content authority enforcement；
8. full replan limit。

---

# 45. Windows Runtime 开发边界

v2.0 第一阶段明确不处理：

- macOS；
- Linux；
- WSL PowerPoint；
- LibreOffice parity；
- cloud PowerPoint rendering；
- remote Office worker；
- containerized PowerPoint。

仅处理：

```text
native Windows
+
Microsoft PowerPoint
```

这样可以最大限度减少 MVP 范围。

---

# 46. 非目标

v2.0 第一阶段不做：

- Web UI；
- Desktop UI；
- Account System；
- Database；
- Cloud Queue；
- Collaborative Editing；
- Real-time PPT Editor；
- 全对象 100% 原生可编辑；
- LibreOffice compatibility parity；
- macOS support；
- Linux support；
- Deck-level AI Reviewer；
- Visual Designer Agent；
- Outline Planner Agent；
- Wireframe Planner Agent。

---

# 47. 风险与控制

## 47.1 PowerPoint COM 稳定性

风险：

- Office hanging；
- file locks；
- COM instance leakage。

控制：

- COM 生命周期管理；
- timeout；
- process cleanup；
- serial / locked Office worker；
- Smoke Test。

## 47.2 Agent 调用耗时

风险：

- Planner / Reviewer 占大部分时间。

控制：

- compact context；
- targeted patch；
- no technical replanning；
- stage reuse；
- limited revisions。

## 47.3 生图文字错误

风险：

```text
Design Image OCR
≠
Approved Content
```

控制：

> Approved Slide Content 始终是文字权威源。

## 47.4 多页状态污染

控制：

- slide workspace isolation；
- per-slide run_state；
- deck_state only summary；
- element / issue ids scoped by slide。

## 47.5 旧入口退化

控制：

- P0 baseline；
- P6 regression；
- backward compatibility tests。

---

# 48. v2.0 最小可发布能力

v2.0 MVP 至少应实现：

```text
Windows installation
↓
Managed Runtime
↓
Content-to-PPT
↓
Approved Outline
↓
Wireframe
↓
Design Images
↓
Existing Single-Slide Runtime
↓
Independent Reviewer
↓
Limited Targeted Revision
↓
Multi-slide Orchestration
↓
PowerPoint COM Assembly
↓
Final Editable PPTX
```

并继续支持：

```text
Image-to-Editable-PPT
```

---

# 49. v2.0 Release 验收定义

正式 Release 前至少满足：

1. Windows + Microsoft PowerPoint 安装与 Verify 成功；
2. 普通任务无需手工切换多个 Python 环境；
3. Runtime Preflight 在 Planner 前执行；
4. 单页正常流程可完成；
5. Technical Failure 不会自动触发 Planner；
6. Local Issue 支持 Targeted Patch；
7. Reviewer timeout 不会造成无限等待；
8. 两次视觉修订上限有效；
9. Stage Resume 有效；
10. Zero-Asset 页面不走无意义资产流程；
11. Content-to-PPT 能生成并确认 Outline；
12. Approved Content 不被 Design OCR 覆盖；
13. Wireframe 能稳定渲染 SVG；
14. Design Image 能进入 Single-Slide Runtime；
15. 多页状态隔离；
16. 有限并发可运行；
17. PowerPoint COM 能组装 Final Deck；
18. Deck QA 能发现页数 / 顺序 / 空页问题；
19. Image-to-Editable-PPT 旧入口继续工作；
20. Claude Code 与 Codex 至少各完成一组端到端正式测试。

---

# 50. v2.0 架构总图

```text
                         User
                          │
                          ▼
                 Claude Code / Codex
                     = Host Agent
                          │
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
      Content-to-PPT          Image-to-Editable-PPT
             │                         │
    Material Understanding      Source Image
             │                         │
    Candidate Outline          Source Slide Content
             │                         │
    User Confirmation                  │
             │                         │
    Approved Outline                   │
             │                         │
   Approved Slide Content              │
             │                         │
    Wireframe Planning                 │
             │                         │
   Wireframe SVG Renderer              │
             │                         │
     Visual Design                     │
             │                         │
      Design Image ────────────────────┘
             │
             ▼
      Runtime Ready Gate
             │
             ▼
       Layout Planner
             │
             ▼
       Shared Validator
             │
             ▼
       Asset Processing
             │
             ▼
          PPT Build
             │
             ▼
      Font / OOXML Audit
             │
             ▼
    Microsoft PowerPoint Render
             │
             ▼
       Structural QA
             │
             ▼
       Visual Reviewer
             │
     ┌───────┼────────┐
     │       │        │
    Pass   Revise   Technical Failure
     │       │        │
     │       ▼        │
     │  Targeted Patch│
     │       │        │
     └───────┴────────┘
             │
             ▼
       Per-slide Result
             │
             ▼
      Limited Parallel Scheduler
             │
             ▼
      PowerPoint COM Assembly
             │
             ▼
           Deck QA
             │
             ▼
      Final Editable PPTX
```

---

# 51. 开发实施优先级

如果资源有限，优先级为：

```text
P0.5 Runtime Hardening
>
P1 Content Planning
>
P2 Wireframe
>
P3 Visual Design
>
P4 Deck Orchestration
>
P5 Deck Assembly
>
P6 Release
```

其中：

> Runtime Hardening 的优先级高于增加新的 Agent 和复杂视觉能力。

因为现有耗时和稳定性问题的主要根因并不是“Agent 不够多”，而是：

- 环境未预检；
- 错误恢复错误；
- Planner 重复调用；
- Validator 不统一；
- 局部问题全量重建；
- Reviewer 无明确退出；
- 无 Stage Reuse。

---

# 52. 最终架构定义

`Content to Editable PPT Skill` v2.0 的整体演进方向可以概括为：

> 保留并强化现有 Image-to-Editable-PPT Single-Slide Runtime，将其作为可复用底座；由 Claude Code / Codex 作为 Host 直接承担材料理解、Outline、Wireframe、Visual Design 和流程编排，只保留 Layout Planner 与 Visual Reviewer 两个独立 Specialist Agent；通过薄 `SKILL.md` 与模块化 references 管理规则，通过 Managed Windows Runtime、Shared Validator、Targeted Patch、Resume 和 Stage Reuse 提升单页稳定性；在其上增加页面级有限并行、Deck State、PowerPoint COM Assembly 和 Deck QA，最终形成从内容材料到可编辑 PowerPoint 的完整 Skill。v2.0 第一阶段仅正式支持 Windows + Microsoft PowerPoint，不让跨平台兼容性阻塞核心能力交付。
