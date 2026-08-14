# DECISIONS.md

> Content to Editable PPT Skill — Architecture Decision Log  
> Status: Active  
> Scope: v2.3 Specification Baseline

本文件记录 `content-to-editable-ppt-skill` 各版本已接受的关键架构与产品决策；当前有效范围由最新未被取代的 ADR 和 v2.3 权威规范共同确定。

它不是需求规格、功能规格或测试计划的替代品。其作用是说明：

- 最终采用了什么方案；
- 为什么采用该方案；
- 该方案带来了哪些后果；
- 后续开发在什么情况下可以修改该决策。

除非新的 ADR 明确替代已有决策，否则 `Status: Accepted` 的决策应视为当前开发基线的一部分。

---

## ADR-001 — v2.0 第一阶段仅正式支持 Windows

**Status:** Accepted

**Decision**

`Content to Editable PPT Skill` v2.0 第一阶段仅正式支持 Windows。

正式参考环境为：

```text
Windows
+
Microsoft PowerPoint Desktop
+
PowerPoint COM
```

**Why**

当前核心 Runtime、PowerPoint 渲染与 Deck Assembly 均以 Microsoft PowerPoint 为主要验证环境。若在 MVP 同时支持 macOS、Linux、LibreOffice 或其他 Office Backend，会显著扩大安装与依赖管理范围、渲染一致性问题、字体兼容问题、Office Automation 差异、测试矩阵与 Release Gate。

第一阶段优先保证 Windows 上的 Full Fidelity 与稳定性。

**Consequences**

- `install.ps1` 是 v2.0 正式安装入口；
- v2.0 不要求 `install.sh`；
- macOS / Linux 不属于 v2.0 Release Gate；
- LibreOffice 不属于 v2.0 正式 Backend；
- 架构可以保留未来扩展点，但不得让跨平台工作阻塞 v2.0。

---

## ADR-002 — Microsoft PowerPoint + COM 是 v2.0 唯一正式 Office Runtime

**Status:** Accepted

**Decision**

v2.0 的 PPT Render、PowerPoint Open / Save Validation 与 Deck Assembly 均以 Microsoft PowerPoint + PowerPoint COM 为正式实现基线。

**Why**

PowerPoint 是最终交付文件的目标编辑器，同时也是现有 Runtime 最可靠的视觉与结构验证环境。

**Consequences**

- 第一版 Deck Assembly 使用 PowerPoint COM；
- 不在 MVP 中实现复杂 OOXML Deck Merge；
- 如果未来增加其他 Backend，应通过新的 ADR 决定。

---

## ADR-003 — 保留并强化现有 Single-Slide Runtime，不重写

**Status:** Accepted

**Decision**

现有 Image-to-Editable-PPT Single-Slide Runtime 继续作为 v2.0 核心底座，通过增量 Hardening 演进。

**Why**

现有项目已经拥有可复用的 Layout Planner、Asset Processing、PPT Build、PowerPoint Render、Structural QA、Visual Reviewer 以及单页 State / Artifact 基础。

当前主要问题集中在环境未提前验证、Planner 重复调用、Validator 契约不一致、局部问题触发全页 Replan、缺乏 Resume / Stage Reuse，以及 Reviewer 技术失败缺乏稳定退出。这些问题可以通过 Runtime Hardening 解决，不需要推翻已有链路。

**Consequences**

- v2.0 首个核心开发阶段为 Single-Slide Runtime Hardening；
- 新 Content-to-PPT 能力必须建立在稳定单页 Runtime 之上；
- 不以“架构统一”为理由重写已经工作的单页模块。

---

## ADR-004 — Host Agent 即 Claude Code / Codex，不新增额外 Host Agent

**Status:** Accepted

**Decision**

Skill 的 Host 是实际执行 Skill 的宿主 Agent，例如 Claude Code 或 Codex。

不创建额外的 `host_agent.yaml` 或等价子 Agent。

**Why**

宿主 Agent 已经具备用户交互、文件读取、工具调用、流程编排与上下文管理。再创建一个 Host 子 Agent 会产生重复职责、额外上下文传递和不必要模型调用。

**Consequences**

Host 直接负责 task routing、material understanding、outline planning、user confirmation、wireframe planning、visual design strategy、image generation orchestration、multi-slide orchestration、issue routing 与 delivery gate。

---

## ADR-005 — v2.0 仅保留两个独立 Specialist Agent

**Status:** Accepted

**Decision**

v2.0 正式保留：

1. `Layout Planner`
2. `Visual Reviewer`

不新增 Outline Planner、Wireframe Planner、Visual Designer Agent、Runtime Agent、Deck Reviewer 或 Revision Agent。

**Why**

只有两类任务明确需要独立 Specialist Agent：设计图到可编辑 PPT 重建规格的专业规划，以及实际 Render 与设计图之间的独立视觉审查。

Outline、Wireframe、Visual Design 等任务可以由 Host 按 Skill Rules 完成。过多 Agent 会增加模型调用成本、延迟、context handoff、state synchronization 与 recovery complexity。

**Consequences**

- 继续演进现有 `agents/planner.yaml`；
- 继续演进现有 `agents/visual_reviewer.yaml`；
- 其他能力通过 `SKILL.md` + `references/` 提供给 Host。

---

## ADR-006 — 使用薄 SKILL.md + 模块化 references

**Status:** Accepted

**Decision**

`SKILL.md` 保持精简，只承担 Skill 定位、task routing、core workflow、critical prohibitions 与 reference loading rules。

详细规则放入 `references/`。

**Why**

避免每个任务都加载完整大型规范，降低上下文成本并减少规则冲突。

**Consequences**

详细规则按职责拆分，例如 content planning、outline contract、wireframe planning、visual design、reconstruction rules、runtime recovery、artifact authority 与 delivery gate。

---

## ADR-007 — Outline 必须确认，确认后成为下游内容权威

**Status:** Accepted

**Decision**

Content-to-PPT 正式流程必须经过：

```text
Candidate Outline
→ User Confirmation
→ Approved Outline
```

用户确认后，下游不得擅自重写已确认内容。

**Why**

Outline 是用户对整套 PPT 内容结构的正式确认点。若下游仍可自由改写，会导致内容漂移、数字/专名/结论变化，并使用户确认失去意义。

**Consequences**

允许下游做换行、文本框拆分和不改变文本的布局适配。

不允许改写、总结、扩写、重新解释、修改数字、修改专名或修改结论。

用户后续修改时，应形成新的 revision，而不是静默覆盖。

---

## ADR-008 — Approved Slide Content 是 Content-to-PPT 的文字权威源

**Status:** Accepted

**Decision**

对于 Content-to-PPT：

```text
Approved Slide Content
=
Text Source of Truth
```

**Why**

Design Image 由生成式图像能力产生，可能出现错字、漏字、OCR 不稳定或字符替换，因此不能让设计图中的文字反向覆盖已确认内容。

**Consequences**

最终 PPT 的正式文字必须来自 Approved Slide Content。

Design Image 中的 OCR 结果仅可用于视觉定位，不得成为正式文字权威。

---

## ADR-009 — Source Slide Content 是 Image-to-Editable-PPT 的文字权威源

**Status:** Accepted

**Decision**

图片直转 PPT 时，在正式 Layout Planner 前形成并冻结 `Source Slide Content`，作为页面文字权威源。

**Why**

直接图片输入没有 Approved Outline，因此需要在进入正式重建前建立稳定文字基线。

**Consequences**

后续 OCR / Vision 再次返回不同文字时，不得静默覆盖已冻结 Source Slide Content。

---

## ADR-010 — Design Image 是视觉权威源，但不是文字权威源

**Status:** Accepted

**Decision**

```text
Design Image
=
Visual Source of Truth
```

它负责 composition、spatial relationships、visual hierarchy、styling、image placement 与 relative proportions。

但其文字内容不得覆盖 Approved Slide Content / Source Slide Content。

**Why**

视觉设计与正式内容需要分别建立稳定权威，才能同时保证视觉还原和内容正确。

**Consequences**

Layout Planner 必须视觉上遵循 Design Image，文本上遵循正式文字权威源。

---

## ADR-011 — Wireframe 由 Host 规划，使用 Deterministic SVG Renderer

**Status:** Superseded by ADR-035

**Decision**

Wireframe 不使用独立 Agent。

流程：

```text
Host Wireframe Planning
→ Wireframe Spec
→ Deterministic Renderer
→ SVG
```

PNG 可作为可选预览格式。

**Why**

Wireframe 是结构规划问题，不需要额外 Specialist Agent；确定性 Renderer 可以降低模型调用、保持输出稳定、方便调试并便于后续自动测试。

**Consequences**

- SVG 是第一版 Wireframe Preview 的主要格式；
- Wireframe 每页都需要逻辑规划；
- Wireframe 不一定必须展示给用户。

该决策对应的实现、测试、PR #12–#16 和 Gate 报告继续作为历史工程证据保留，但不再定义当前正式 P2 产品行为。

---

## ADR-012 — Visual Design 由 Host 调宿主可用生图能力

**Status:** Accepted

**Decision**

v2.0 不建立 Visual Designer Agent 或固定图像模型 Adapter。

流程：

```text
Approved Slide Content
+
Wireframe
+
User Visual Requirements
+
Deck Visual Direction
↓
Host Visual Design Brief
↓
Available Image Generation Capability
↓
Design Image
```

**Why**

不同宿主环境可能具有不同图像生成能力。MVP 不应因为绑定某一个特定图像模型而增加不必要耦合。

**Consequences**

Skill 定义视觉输入、输出和质量要求，但不绑定固定 Visual Designer Agent。

---

## ADR-013 — 页面设计默认采用 ≤5 页全量、>5 页 Sample-first

**Status:** Superseded by ADR-038

**Decision**

默认编排策略：

```text
≤ 5 pages
→ generate all design images
```

```text
> 5 pages
→ representative sample first
```

**Why**

短 Deck 额外确认 Sample 的收益有限；较长 Deck 若先验证代表性页面，可以减少全量视觉方向错误带来的返工。

**Consequences**

该规则只是默认 heuristic。用户可以明确覆盖，例如 4 页先看 Sample 或 20 页直接全部生成。用户要求优先。

---

## ADR-014 — Image-to-Editable-PPT 保持独立入口

**Status:** Accepted

**Decision**

用户直接提供设计图 / Screenshot 时，继续直接进入 Single-Slide Runtime。

不强迫其经过 Outline、Wireframe 或 Visual Design。

**Why**

现有 Image-to-Editable-PPT 是已经成立的核心能力，也是 v2.0 需要保持的 Backward Compatibility。

**Consequences**

v2.0 存在两条正式入口：`Content-to-PPT` 和 `Image-to-Editable-PPT`。

Deck 层位于现有 Single-Slide Runtime 之上，而不是替代它。

---

## ADR-015 — 局部问题优先 Targeted Patch，不默认 Full Replan

**Status:** Accepted

**Decision**

局部 Reconstruction / Visual Issue 应首先：

```text
Issue
→ Targeted Patch
→ Shared Validator
→ rerun affected stages
```

不得默认重新规划整页。

**Why**

现有耗时问题的主要来源之一，是局部问题触发完整 Planner 重跑和全链路重建。

**Consequences**

Layout Planner 需要支持 Patch Mode，并限定 target elements、restricted paths 与 allowed changes。只有真正的全局语义 / 结构问题才允许 Limited Full Replan。

---

## ADR-016 — 技术错误不得触发新的语义 Planner 调用

**Status:** Accepted

**Decision**

PowerPoint Render temporary failure、file lock、dependency execution failure、Reviewer technical timeout 等技术问题不得自动触发新的语义 Layout Planner 调用。

**Why**

技术失败并不意味着 Reconstruction Spec 错误。重新 Planner 不解决技术根因，同时增加模型耗时并可能引入新的语义变化。

**Consequences**

技术错误进入 `Technical Retry / Runtime Repair / Resume`，而不是 Semantic Replan。

---

## ADR-017 — Technical Retry 每阶段最多 2 次

**Status:** Accepted

**Decision**

```text
max_technical_retries_per_stage = 2
```

**Why**

必须禁止无限重试，同时允许短暂技术故障有有限恢复机会。2 次是当前 MVP 的工程折中：比一次更具容错性，又避免三次以上低收益重复。

**Consequences**

流程：

```text
initial attempt
→ retry 1
→ retry 2
→ explicit failure path
```

不得出现 retry 3。

Technical Retry 与 Visual Revision 计数器必须分离。

---

## ADR-018 — 用户模式最多进行 2 轮 Targeted Visual Revision

**Status:** Accepted

**Decision**

页面视觉修订最多 2 轮 targeted visual revisions。

**Why**

避免 Reviewer / Planner 之间形成开放式无限修订循环。

**Consequences**

若第二轮修订后仍存在 Major / Critical，则进入 `revision_required / failed`，不得自动开启第三轮。

技术重试不消耗视觉修订次数。

---

## ADR-019 — Visual Reviewer 必须尝试调用，但技术不可用时允许受控降级

**Status:** Accepted; Content-to-Deck amended by ADR-038

**Decision**

正常最终页面必须尝试独立 Visual Reviewer。

若 Reviewer 因技术原因 timeout / unavailable，并且 Structural QA、Content Gate 与 Editability Gate 通过，则允许：

```text
delivered_with_warnings
```

并记录：

```text
visual review incomplete
```

**Why**

Reviewer 的独立性很重要，但 Reviewer 服务技术故障不应造成无限等待、无意义 Planner 重跑或已经结构正确的页面无法退出。

**Consequences**

如果 Reviewer 实际返回 Major / Critical，则不得伪装成 timeout 走降级路径。

---

## ADR-020 — 正常交付要求 Critical = 0 且 Major = 0

**Status:** Accepted

**Decision**

Visual Gate：

```text
Critical = 0
Major = 0
```

Minor 不设置固定数量上限。

**Why**

Minor 数量与页面复杂度高度相关，简单计数不能稳定代表质量。

**Consequences**

Minor 可以交付，但必须作为 Reviewer Evidence 保留。

---

## ADR-021 — 不设置固定总运行时间 SLA

**Status:** Accepted; call budgets clarified by ADR-038

**Decision**

v2.0 不规定 `N pages must finish within X minutes` 作为 Release Gate。

**Why**

Skill 的优先级为：

```text
内容准确性
>
可编辑性
>
视觉质量
>
运行速度
```

固定总时长 SLA 可能诱导开发通过减少 Reviewer / QA 或降低质量来“达标”。真正需要控制的是无效 Planner 调用、重复 Asset Processing、重复 Build、不必要 Full Replan、无退出 Reviewer Waiting 以及未复用已通过 Stage。

**Consequences**

测试需要记录 timing，但性能 Gate 主要关注“无效重复工作”。

---

## ADR-022 — Passed Stage 在输入未变化时应复用

**Status:** Accepted

**Decision**

原则：

```text
stage passed
+
relevant input unchanged
=
reuse
```

**Why**

减少没有质量收益的重复执行。

**Consequences**

Runtime 必须逐步支持 Resume、Stage Reuse、dependency-based invalidation 与 artifact identity。

例如 Build 已通过而 Render 失败时，不应重新 Planner / Asset / Build。

---

## ADR-023 — Single-Slide 详细状态继续由 run_state 管理

**Status:** Accepted

**Decision**

现有 `run_state` 继续作为单页任务详细执行状态权威。

不创建第二套并行的 Single-Slide authoritative state。

**Why**

避免状态源重复、冲突和恢复歧义。

**Consequences**

新功能应扩展或兼容现有 run_state，而不是另建一套等价状态系统。

---

## ADR-024 — Deck State 只负责多页汇总，不复制单页内部状态

**Status:** Accepted

**Decision**

新增 `deck_state` 仅负责 page list、order、per-slide summary、assembly、Deck QA 与 final delivery status。

**Why**

单页已经有 run_state。Deck 层不应复制完整 Planner / Build / Reviewer 内部状态。

**Consequences**

```text
run_state
=
single-slide detailed state
```

```text
deck_state
=
deck-level orchestration state
```

两者职责分离。

---

## ADR-025 — Runtime Manifest 与任务状态分离

**Status:** Accepted

**Decision**

`runtime-manifest` 用于记录 Managed Runtime / Environment 状态，不属于 run_state 或 deck_state。

**Why**

环境生命周期与单次任务生命周期不同。

**Consequences**

正式状态模型：

```text
runtime-manifest
≠
run_state
≠
deck_state
```

---

## ADR-026 — 多页采用有限页面级并行，并保持页面隔离

**Status:** Accepted

**Decision**

多页任务允许 Limited Page-level Parallelism。并发数配置化，不硬编码。

**Why**

页面之间大部分重建工作相互独立，适度并发可以减少 Deck 总耗时；无限并发则会增加资源竞争、PowerPoint COM 不稳定、Agent 上下文污染与状态串页风险。

**Consequences**

每页必须隔离 workspace、run_state、assets、reconstruction spec、render、QA、reviewer result 与 patch。

PowerPoint COM 阶段可以根据稳定性采用串行 Worker / Lock。

---

## ADR-027 — v2.0 Deck Assembly 使用 PowerPoint COM

**Status:** Accepted

**Decision**

多页结果采用：

```text
Per-slide PPTX
→ PowerPoint COM
→ Final Deck PPTX
```

**Why**

第一版优先保证正确性、Office 原生兼容性和实现复杂度可控。

**Consequences**

v2.0 不开发完整通用 OOXML Merge Engine。未来若有充分需求，可单独评估 Direct Deck Builder / OOXML Merge。

---

## ADR-028 — Deck QA 第一版采用 Deterministic QA，不新增 Deck Reviewer Agent

**Status:** Accepted; Deck consistency checkpoint added by ADR-038

**Decision**

Deck-level 第一版只进行确定性 QA。

至少检查 slide count、slide order、openability、blank / missing / duplicate slides、page dimensions 与 assembly consistency。

**Why**

页面级 Visual Reviewer 已负责视觉审核。新增 Deck Reviewer Agent 在 MVP 中收益有限。

**Consequences**

需要 Deck-level AI Review 时，应作为未来独立功能评估。

---

## ADR-029 — 内容准确性优先级高于视觉速度优化

**Status:** Accepted

**Decision**

v2.0 质量优先级：

```text
内容准确性
>
可编辑性
>
视觉质量
>
运行速度
```

**Why**

最终 PPT 的核心价值首先是内容正确，其次是可编辑，再其次是视觉质量。速度优化不得破坏前三项。

**Consequences**

不得为了减少耗时而跳过内容权威检查、整页截图冒充可编辑、默认取消必要 Reviewer 或降低关键 Structural QA。

---

## ADR-030 — Standard B Editability 是 v2.0 正式编辑性目标

**Status:** Accepted

**Decision**

v2.0 不追求所有视觉元素 100% PPT 原生化。

正式目标：

- 主要文字可编辑；
- 主要 / 基础结构可编辑；
- 复杂视觉元素允许保留为图像；
- 不得用整页 Raster Screenshot 冒充可编辑 PPT。

**Why**

全对象 100% 原生化会显著扩大 Reconstruction 复杂度，并不一定带来与成本相匹配的用户价值。

**Consequences**

Editability QA 应围绕主要内容和主要结构，而不是要求所有装饰细节原生化。

---

## ADR-031 — Deterministic 组件严格测试，生成式 Agent 采用契约验收

**Status:** Accepted

**Decision**

测试方法分离：

```text
Deterministic Components
→ strict assertions
```

```text
Generative Agents
→ contract-based acceptance
```

**Why**

生成式输出具有合理随机性，逐字 / 逐像素 Golden Match 不适合 Agent 输出；而状态、页数、Retry、内容一致性等确定性行为必须严格判断。

**Consequences**

Approved Content equality、slide count、retry count 等必须严格；Outline wording 不要求逐字一致，但必须满足契约；Planner 不要求完全相同布局值，但必须通过 Schema / Semantic Contract。

---

## ADR-032 — v2.0 Release 问题采用 Blocking / Warning / Deferred 三级分类

**Status:** Accepted

**Decision**

正式测试和 Release Issue 分类：

```text
Blocking
Warning
Deferred
```

**Why**

需要明确区分核心正确性失败、可接受的非阻塞问题，以及当前版本根本不承诺的功能。

**Consequences**

正式 Release 要求：

```text
Blocking Issues = 0
```

Warning 必须记录；Deferred 不影响 v2.0 Release。

---

## ADR-033 — P0 必须先冻结 Baseline，再修改 Single-Slide Runtime

**Status:** Accepted

**Decision**

v2.0 开发进入 Runtime Hardening 前，必须先完成 P0 Baseline Freeze。

固定 6 类代表性 Single-Slide Baseline：

1. 纯文字 + 基础形状；
2. 卡片 + 图标；
3. 图片 + 文字；
4. 流程 / Connector；
5. 复杂信息图；
6. Zero-Asset 页面。

**Why**

没有稳定 Baseline，就无法证明 Hardening 是否修复了问题、是否引入回归、是否减少 Planner 调用、是否影响视觉与编辑性。

**Consequences**

P0 阶段只记录真实现状，不顺手修复 Runtime。

---

## ADR-034 — v2.0 开发按 P0 → P0.5 → P1 → P6 Gate 推进

**Status:** Accepted

**Decision**

开发顺序：

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

**Why**

Content-to-PPT、Visual Design 和 Deck 能力最终都依赖 Single-Slide Runtime。先扩大功能、后修底座会将现有问题放大到多页场景。

**Consequences**

不建议在 P0.5 Gate 未通过前直接大规模开发 P1–P5。

---

## ADR-035 — P2 Wireframe 采用大模型生成的 Markdown 文字线稿

**Status:** Accepted

**Supersedes:** ADR-011

**Decision**

P2 的正式 Wireframe 是 Host 大模型逐页生成的 Markdown 文字线稿，用于表达每页真实内容、页面布局草稿、信息层级和内容关系。

正式产物为：

```text
wireframes/deck-wireframe.md
wireframes/wireframe-manifest.json
```

`deck-wireframe.md` 是唯一正式线稿内容本体。`wireframe-manifest.json` 只记录 Deck、P1 Authority、页序、Content Ref、Revision、文件 Hash 和接受状态，不保存坐标、BBox、Region Graph、SVG 路径或最终视觉风格。

正式流程：

```text
P1 Approved Slide Content
→ P1 Authority Validation
→ Host Markdown Wireframe Pass
→ Markdown Structure Validation
→ Content Binding / Drift Validation
→ Bounded Contract Correction
→ 默认在聊天中逐页展示
→ Accepted / Layout Revision / Return to P1
```

P2 不再以 SVG、PNG、精确坐标、BBox、Region Graph 或 Deterministic SVG Renderer 作为正式产物或生产路径。

**Why**

P2 的产品目标是让用户和 Host 低成本讨论“每页放什么、如何布局”，而不是建立第二套图形渲染系统。Markdown 文字线稿更适合聊天展示、用户修改和 P3 视觉设计输入，同时可以通过 P1 Authority、固定 Metadata Binding 和极薄 Manifest 保持机器可验证性。

**Consequences**

- 已合并的 PR #12–#16、SVG P2 实现、测试和 `reports/p2/p2-wireframe-gate.json` 作为历史技术证据保留，不回滚、不关闭、不改写；
- 旧 SVG P2 Gate 不等于新的 Markdown P2 Gate；
- P2 状态重新打开，Markdown P2 Implementation 与新 Gate 通过前不得进入 P3；
- `deck-wireframe.md` 的“页面内容”必须逐字绑定 Approved Slide Content，布局线稿可用真实短句或 Content Block 标签表示位置；
- 默认向用户展示整套线稿；明确跳过查看只取消暂停，不取消生成；
- 废弃 SVG 作为 P2 Wireframe 表示，不影响 SVG 作为 PPT Runtime 视觉素材格式；`sanitize_svg.py`、SVG Asset Manifest、`validate_assets.py` 和 Builder SVG 支持继续保留。

---

## ADR-036 — Tabler-first Visual Asset Resolution

**Status:** Accepted; production fallback narrowed by ADR-039

**Decision**

P2.1 只冻结 Visual Placeholder 的语义、当前页 P1 内容来源绑定和布局位置；不得决定图库、图标文件或 SVG。P3.1 v1 以固定的 Tabler Icons `v3.46.0` outline 作为唯一正式图标库，并将 Placeholder 解析为不可变 Icon Resolution Record。

只有唯一 canonical icon name 或 official alias 可以自动选择；其他候选由当前 P3 Host Pass 从确定性 Top-K 中选择。找不到单图标时依次尝试最多两个 Tabler 图标组合、受限 Programmatic SVG 和 Raster/Image Handoff。

任意 SVG 都必须经过 Normalize、`sanitize_svg.py` 和 `validate_assets.py`。Design Preview Compositor 和 PPT Runtime 必须实际消费 Asset Manifest 绑定的同一 Sanitized SVG Source；生成模型不得重绘或替代已解析图标。

P3.1 只建立资产解析与物化能力，不生成正式 Design Preview，也不代表完整 P3 Visual Design 完成。

**Consequences**

- P3 Resolver 只读取 Accepted P2 Manifest 的 Placeholder 字段，不重新解析 Markdown 业务数据；
- Resolution Record 写入一次，Normalize/Sanitize Hash 记录在 Asset Manifest；
- Tabler 固定为 `v3.46.0` / `8ac7d81b72ece11072ef25ea9fd92e80c6f3c9fc`；
- `@resvg/resvg-js` 固定为 `2.6.2`，只用于消费验证和后续 Preview Composition；
- 不新增 Icon Agent、Icon Reviewer 或在线检索；
- Lucide、Phosphor、Iconify 和 OpenMoji 属于 Future Work。

---

## ADR-037 — Approved Design Preview 是确认后的视觉权威

**Status:** Accepted

**Decision**

Content-to-PPT 必须先形成高质量图片版页面并取得用户确认。确认后的 `Approved Design Preview` 是页面构图、空间关系、视觉层级、样式、资产位置和相对比例的视觉权威；P1 Approved Slide Content 仍是唯一正式文字权威。

```text
Approved Content + Wireframe + Resolved Assets
→ Design Preview Candidate
→ User Confirmation
→ Approved Design Preview
→ Visual Reconstruction Spec
→ Editable PPT
```

最终 PowerPoint Render 必须与 Approved Design Preview 比较。目标是感知结构保真，不要求像素级一致。

**Why**

纯结构化规则直接生成 PPT 容易得到可编辑但设计质量普通的页面；只看图片重新猜测又会丢失已冻结的内容、结构和资产。双 Authority 可以同时保持视觉质量、内容准确性和可编辑性。

**Consequences**

- 生图模型不得成为正式文字权威；
- P4 必须建立 Preview 元素到 PPT 对象的 Visual Reconstruction Spec；
- 用户确认后的 Design Preview 不得被 Runtime 自由改版；
- 正常交付要求视觉 Critical = 0 且 Major = 0；
- 禁止使用含正式内容的整页位图代替可编辑重建。

---

## ADR-038 — Deck Prompt Package、Style Anchor 与调用预算是强制机制

**Status:** Accepted

**Decision**

所有 Deck 在批量生成设计图前都必须冻结 Deck Visual System、Prompt Package、Negative Prompt、生成参数和一个用户确认的主 Style Anchor。每页 Prompt 由确定性 Compiler 注入页面内容、线稿、视觉占位、已解析资产和页面角色；Host 不得逐页自由重写整体视觉风格。

```text
Deck Visual Direction Host Pass = 1
Prompt Compilation Agent Calls = 0
Style Anchor Generation = 1
Initial Design Generation <= 1 per slide
Automatic Design Regeneration = 0
Automatic Full-deck Redesign = 0
Technical Retry <= 2 per stage
Deck Consistency Review = 1
Per-page Reviewer = exception pages only
```

**Why**

固定 Prompt 只能降低随机漂移，Style Anchor 和 Deck 一致性审核才能形成实际跨页约束。先确认代表页再批量生成，可避免全套页面因整体风格错误而返工。调用预算、页面级缓存和 Fail-Fast 用于控制时间，而不是通过降低内容、编辑性或视觉质量换取速度。

**Consequences**

- ADR-013 的页数分支被替代，所有 Deck 默认先确认 Style Anchor；
- Content-to-Deck 全页运行确定性 QA，只将异常页交给页面 Reviewer；
- 使用现有 Visual Reviewer 完成一次 Deck Consistency Review，不新增 Deck Reviewer Agent；
- 独立 Image-to-Editable-PPT 继续保留逐页 Reviewer Gate；
- 不设置固定总时长 SLA，但必须记录调用、重试、缓存、复用和阶段耗时；
- 任一确定性 Blocking 在后续模型调用前停止。

---

## ADR-039 — 标准 SVG 只来自准确匹配图库，缺失时从确认设计图提取

**Status:** Accepted

**Decision**

标准 SVG 只用于固定 Tabler 库中能够准确表达 Visual Placeholder 语义的图标。没有准确匹配时进入 `Raster Handoff Pending`；在 Design Preview 获得用户确认后，从 Approved Design Preview 提取对应小型视觉元素作为独立 PNG。

```text
Accurate Tabler SVG
→ Sanitized SVG

No accurate match
→ Raster Handoff Pending
→ Approved Design Preview
→ Target Element Extraction
→ Independent PNG
```

Two-icon Composition 和 Programmatic SVG 不再属于正式生产回退链。

**Why**

强行组合或程序化绘制语义不准确的 SVG 会牺牲用户确认的视觉效果，并把复杂视觉错误地扩大为矢量绘制问题。复杂视觉只需对象级可移动、缩放和替换，不要求内部路径全部可编辑。

**Consequences**

- ADR-036 的 Tabler Core、离线解析、不可变 Resolution Record、Sanitize 和同源 Hash 继续有效；
- ADR-036 的 Composition/Programmatic 正式回退被本决策取代；
- 历史代码、测试和 Gate 报告保留为工程证据，但不得进入正式 Skill 路由；
- 提取必须绑定 Approved Preview Hash、Visual Ref、Crop BBox 和 PNG Hash；
- 提取不得包含正文、数字、标签、无关对象或整页；
- 低分辨率、背景融合、遮挡或无法分离时返回 `extraction_failure`。

---

# 决策变更规则

如果后续需要修改 `Accepted` ADR，应遵循：

```text
发现新的工程证据 / 产品需求
↓
明确指出受影响的 ADR
↓
提出替代决策
↓
说明原因与后果
↓
更新相关规范
↓
新增或修改 ADR 状态
```

不建议直接删除历史决策。

若某条决策被替代，可改为：

```text
Status: Superseded by ADR-XXX
```

若确认不再适用，可改为：

```text
Status: Deprecated
```

---

# 与其他规范的关系

本文件只记录关键决策及其原因。

如果存在更详细执行要求，应以对应正式规范为准：

- 产品范围 → Requirements；
- 功能行为 → Functional Specification；
- 质量标准 → NFR；
- Agent 权限 → Agent Contract；
- Runtime 安装 → Runtime Installation Specification；
- 单页执行 / Recovery → Single-Slide Runtime Specification；
- Artifact / State → Artifact & State Authority Contract；
- 总体模块与开发阶段 → Architecture & Development Plan；
- 测试与 Release Gate → Test & Acceptance Plan。

如果发现正式规范之间存在冲突：

> 不应由 Coding Agent 自行选择其中一个并继续实现。

应停止相关实现，报告冲突并提出最小化规范修订方案。

---

# 当前基线

当前 v2.3 Specification Baseline 的核心方向为：

```text
Windows only
+
Microsoft PowerPoint / COM
+
Existing Single-Slide Runtime Hardening
+
Host = Claude Code / Codex
+
Layout Planner
+
Visual Reviewer
+
Thin SKILL.md + references
+
Content Authority / Visual Authority separation
+
Targeted Patch
+
Bounded Retry
+
Resume / Stage Reuse
+
Limited Page Parallelism
+
PowerPoint COM Deck Assembly
+
Gate-based Development
+
P2 Markdown Wireframe
+
Legacy SVG P2 Isolation
+
Approved Design Preview Visual Authority
+
Deck Visual System + Locked Prompt Package
+
Style Anchor before batch generation
+
Accurate Tabler SVG or Approved Preview extraction
+
Constrained Visual Reconstruction
+
Call budgets + page-level reuse
```
