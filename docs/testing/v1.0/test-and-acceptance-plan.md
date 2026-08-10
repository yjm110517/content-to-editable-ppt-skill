# Content to Editable PPT Skill 测试与验收计划 v1.0

> 英文名：Content to Editable PPT Skill Test & Acceptance Plan v1.0

## 1. 文档目的

本文档定义 `Content to Editable PPT Skill` v2.0 的测试策略、验收范围、正式测试环境、Baseline、单页与多页测试规模、Agent 测试方法、视觉质量 Gate、错误恢复测试、性能回归方法、Host 兼容测试、Clean Windows 安装测试以及 Release Gate。

本文档的目标不是穷举每一个未来可能出现的测试，而是将已经冻结的需求、功能、非功能要求、Agent 契约、Runtime 契约和 Artifact / State 契约转化为：

```text
可执行测试
+
明确通过标准
+
明确失败标准
+
明确测试证据
+
明确是否阻塞Release
```

本文档主要回答：

> 什么必须测试、在哪些环境测试、用什么规模测试、哪些结果算通过、哪些问题必须阻塞 v2.0 发布。

---

# 2. 适用范围

本测试计划适用于：

```text
Content-to-PPT
```

和：

```text
Image-to-Editable-PPT
```

两条正式入口。

覆盖：

- Windows Runtime 安装；
- Runtime Bootstrap；
- Fast Preflight；
- Runtime Repair；
- Layout Planner；
- Shared Validator；
- Asset Processing；
- PPT Build；
- PowerPoint Render；
- Structural QA；
- Visual Reviewer；
- Targeted Patch；
- Technical Retry；
- Resume / Stage Reuse；
- Content Planning；
- Wireframe；
- Visual Design；
- Multi-slide Orchestration；
- PowerPoint COM Deck Assembly；
- Deck QA；
- Claude Code / Codex Host E2E；
- Release Regression。

不属于 v2.0 Release 阻塞范围：

- macOS；
- Linux；
- LibreOffice；
- 跨平台视觉一致性；
- 50 页以上超长 Deck 压力测试；
- Deck-level AI Reviewer；
- Visual Designer Agent；
- Outline Planner Agent；
- Wireframe Planner Agent。

---

# 3. 已冻结的测试决策

v1.0 正式冻结以下十项测试策略。

| 编号 | 决策 | 冻结结果 |
|---|---|---|
| TDS-01 | 正式运行环境 | Windows 11 x64 + Microsoft PowerPoint Desktop |
| TDS-02 | Clean Install | Release 前必须完成至少一次 Clean Windows E2E |
| TDS-03 | Host Gate | Claude Code 与 Codex 均至少通过一套正式 E2E |
| TDS-04 | 单页 Baseline | 固定 6 个代表性页面 |
| TDS-05 | Deck E2E 规模 | 3 页、5 页、8–10 页三档 |
| TDS-06 | Agent 测试方法 | Deterministic 严格断言；Agent 使用契约验收 |
| TDS-07 | Visual Gate | Critical = 0，Major = 0；Minor 不设置硬数量阈值 |
| TDS-08 | Performance | 不设置总时间 SLA；重点测试无效重复工作 |
| TDS-09 | Technical Retry | 每阶段最多自动重试 2 次 |
| TDS-10 | Release 分级 | Blocking / Warning / Deferred |

说明：

> TDS-01 与 TDS-02 分别冻结正式参考环境和 Clean Windows 验收环境；本表共包含十项正式测试决策。

---

# 4. 正式测试环境

## 4.1 Reference Environment

v2.0 正式测试基准：

```text
Operating System:
Windows 11 x64

Office:
Microsoft PowerPoint Desktop

Automation:
PowerPoint COM

Hosts:
Claude Code
Codex
```

具体 Office Build、Python 版本、Node 版本应记录在测试报告中，但不在本规范中硬编码。

---

# 5. 测试环境分层

## 5.1 Development Environment

用于：

- Unit Test；
- Integration Test；
- Runtime Test；
- Agent Forward Test；
- Regression；
- Failure Injection。

允许环境中已经存在：

- Python；
- Node；
- PowerPoint；
- Git；
- Claude Code；
- Codex；
- 开发工具。

## 5.2 Clean Windows Environment

Release Candidate 必须至少在一个尽量干净的 Windows 环境上完成：

```text
Skill Installation
↓
install.ps1
↓
Runtime Bootstrap
↓
Verify
↓
PowerPoint Detection
↓
COM Smoke Test
↓
Image-to-Editable-PPT E2E
↓
Content-to-PPT E2E
```

可使用：

- 干净虚拟机；
- Windows Sandbox；
- 独立测试机；
- 其他可证明未依赖开发机已有项目环境的 Windows 环境。

### Blocking Condition

如果：

```text
开发机通过
Clean Windows无法安装或运行
```

则：

```text
Release = BLOCKED
```

---

# 6. Host Compatibility Gate

## 6.1 Claude Code

至少完成一套真实 E2E：

```text
User Request
↓
Skill Routing
↓
References Loading
↓
Outline / Source Content
↓
Wireframe / Design（若Content-to-PPT）
↓
Layout Planner
↓
Runtime
↓
Visual Reviewer
↓
Final PPTX
```

## 6.2 Codex

同样至少完成一套真实 E2E。

## 6.3 不要求重复所有底层测试

以下测试属于 Runtime / deterministic layer：

- Validator；
- State；
- Build；
- Render；
- QA；
- COM；
- Retry；
- Resume；
- Deck Assembly。

不要求在 Claude Code 和 Codex 分别全部重跑。

正式 Host Gate：

```text
Claude Code E2E = PASS
AND
Codex E2E = PASS
```

否则：

```text
Release = BLOCKED
```

---

# 7. 测试层级

v2.0 测试分为七层。

```text
L1 Unit / Deterministic
L2 Single-Slide Integration
L3 Agent Contract / Forward
L4 Failure & Recovery
L5 Deck Integration
L6 Host End-to-End
L7 Clean Install / Release Regression
```

---

# 8. Deterministic Test 原则

确定性组件必须采用严格断言。

例如：

- schema 是否通过；
- page count 是否一致；
- page order 是否一致；
- text 是否完全一致；
- retry count 是否正确；
- state 是否正确；
- file 是否存在；
- PPT 是否打开；
- run_state 是否更新；
- deck_state 是否串页；
- Stage Reuse 是否发生；
- Planner 是否被错误重复调用。

若预期：

```text
Approved Content = A
```

而最终 PowerPoint 原生文本为：

```text
B
```

则直接：

```text
FAIL
```

不允许以“语义相近”为理由通过。

---

# 9. Agent Test 原则

Agent 输出具有生成随机性，因此不采用逐字 Golden Match。

测试的是：

```text
Contract Compliance
```

而不是：

```text
Exact Natural Language Match
```

## 9.1 Outline

检查：

- 必要页面是否存在；
- 用户要求是否覆盖；
- 是否存在明显越权编造；
- 是否经过用户确认；
- 确认后是否被冻结。

## 9.2 Wireframe

检查：

- 页面区域是否合法；
- 页面主要内容均有位置；
- 不改写 Approved Slide Content；
- Wireframe Spec 可被 Renderer 正确消费。

## 9.3 Layout Planner

检查：

- 输出 Schema 合法；
- Approved Content 没有被改写；
- element id 稳定；
- bbox 合法；
- connector 合法；
- native / raster 策略合法；
- Targeted Patch 只修改允许区域。

## 9.4 Visual Reviewer

检查：

- 独立上下文；
- 输出 Schema 合法；
- Issue 可定位；
- severity 合法；
- target_element_ids 合法；
- 不直接修改 PPT；
- 不拥有 Delivery 权。

---

# 10. P0 Baseline Freeze

## 10.1 目标

冻结现有 Image-to-Editable-PPT Runtime 的可回归基线。

## 10.2 固定 6 个 Baseline

### B01 — 纯文字 + 基础形状

覆盖：

- native text；
- 基础 rectangle / rounded rectangle；
- 字号；
- 对齐；
- 层级。

### B02 — 卡片 + 图标

覆盖：

- 图标；
- 卡片；
- z-order；
- spacing；
- native / raster decomposition。

### B03 — 图片 + 文字

覆盖：

- image placement；
- crop；
- asset handling；
- text-image alignment。

### B04 — 流程 / 连接线

覆盖：

- connector topology；
- endpoint；
- arrow direction；
- node relationships。

### B05 — 复杂信息图

覆盖：

- 综合重建；
- 多元素关系；
- visual hierarchy；
- mixed native / raster strategy。

### B06 — Zero-Asset 页面

覆盖：

- 无 raster / svg asset；
- Zero-Asset Fast Path；
- 不执行无意义资产处理。

---

# 11. Baseline 证据

每个 Baseline 至少保存：

```text
source image
approved/source content
planner spec
processed assets
pptx
render
structural qa
reviewer result
timing
planner call count
reviewer call count
revision count
```

Baseline 不是像素级 Golden。

Baseline 用于：

- 行为回归；
- 编辑性回归；
- 调用次数回归；
- 视觉严重性回归；
- Runtime 稳定性回归。

---

# 12. Single-Slide Integration Tests

## SSI-01 正常简单页面

**输入：**

B01。

**预期：**

```text
Preflight
→ Planner
→ Validation
→ Build
→ Render
→ QA
→ Reviewer
→ Delivered
```

**Pass：**

- PPTX 正常生成；
- PowerPoint 能打开；
- 主要文字 native editable；
- Reviewer 无 Major / Critical。

**级别：**

Blocking。

---

## SSI-02 Zero-Asset Fast Path

**输入：**

B06。

**预期：**

```text
asset_count = 0
→ skip unnecessary asset pipeline
```

**Pass：**

- 不执行无意义 crop / svg sanitize；
- 页面仍正常构建和审核。

**级别：**

Blocking。

---

## SSI-03 Approved Content Protection

**输入：**

Design Image 中故意含错误文字；Approved Slide Content 为正确文字。

**预期：**

最终 PPT 使用 Approved Slide Content。

**Pass：**

逐字一致。

**级别：**

Blocking。

---

## SSI-04 Source Slide Content Freeze

**输入：**

图片直转 PPT，第二次 Vision/OCR 返回不同文字。

**预期：**

正式重建继续使用冻结的 Source Slide Content。

**级别：**

Blocking。

---

## SSI-05 Rasterization Evasion

模拟 Builder 尝试将整页 Design Image 作为全页截图交付。

**预期：**

Structural QA Fail。

**级别：**

Blocking。

---

# 13. Shared Validator Tests

## VAL-01 Schema Invalid

缺少必填字段。

预期：

```text
validation_failure
```

不得 Build。

## VAL-02 Connector Invalid

connector endpoint 非法。

预期：

```text
local specification issue
→ Targeted Patch
```

不得 Full Replan。

## VAL-03 Unsafe Path

资产路径越出允许目录。

预期：

```text
validation failure
```

不得访问越权路径。

## VAL-04 Same Validator Contract

Planner Candidate 和正式 Build Input 使用同一核心校验逻辑。

预期：

> 不出现 Candidate Pass、Finalizer 因完全不同规则立即 Reject 的契约漂移。

以上均为 Blocking。

---

# 14. Failure & Recovery Tests

## FR-01 Environment Preflight Failure

模拟：

- Python package 缺失；
- Node dependency 缺失。

预期：

```text
Preflight Fail
→ Runtime Repair
→ Reverify
→ Continue
```

关键断言：

```text
Layout Planner call count before Runtime Ready = 0
```

Blocking。

---

## FR-02 Repair Failure

模拟无法恢复的环境问题。

预期：

```text
environment_failure
```

且：

- Planner 不调用；
- 不生成新的 Outline；
- 不无限重试。

Blocking。

---

## FR-03 Render Technical Failure

模拟 Render 首次失败。

预期：

```text
Render Fail
→ Technical Retry
```

关键断言：

```text
additional Planner calls = 0
```

Blocking。

---

## FR-04 Technical Retry Limit

连续让同一 Stage 技术失败。

正式上限：

```text
max_technical_retries_per_stage = 2
```

预期：

```text
initial attempt
→ retry 1
→ retry 2
→ stop
```

不得 retry 3。

Blocking。

---

## FR-05 Local Connector Patch

Reviewer / QA 返回 connector 局部错误。

预期：

```text
Targeted Patch
→ Build
→ Render
→ QA
→ Reviewer
```

关键断言：

```text
Full Semantic Replan = 0
```

Blocking。

---

## FR-06 Resume from Render

状态：

```text
Planner = pass
Assets = pass
Build = pass
Render = fail
```

恢复：

```text
Resume from Render
```

关键断言：

- Planner 不重复；
- Assets 不重复；
- Build 不重复。

Blocking。

---

## FR-07 Reviewer Timeout

状态：

```text
Structural QA = pass
Reviewer = technical timeout
```

预期：

```text
delivered_with_warnings
```

并记录：

```text
visual review incomplete
```

不得重新 Layout Planner。

Blocking（对降级逻辑而言）。

---

## FR-08 Reviewer Major Issue

Reviewer 正常返回 Major。

预期：

```text
revision_required
→ Targeted Patch
```

不得走 timeout 降级。

Blocking。

---

## FR-09 Two Visual Revisions

流程：

```text
Initial
→ Major
→ Revision 1
→ Major
→ Revision 2
→ Major
```

预期：

```text
failed
```

不得 Revision 3。

Blocking。

---

# 15. Visual Quality Gate

正式页面通过条件：

```text
Critical = 0
Major = 0
Reviewer Status = pass
```

Minor：

- 可以存在；
- 不设置固定数量上限；
- 需要保留 Reviewer Evidence。

## 15.1 Major / Critical 示例

包括但不限于：

- 明显错位；
- 文本溢出；
- typography hierarchy 错误；
- connector 关系错误；
- crop 错误；
- large background seams；
- severe style drift；
- key proportion 错误；
- missing key elements；
- full-page rasterization；
- Approved Content 缺失或被改写。

## 15.2 Minor 示例

例如：

- 阴影略有不同；
- gradient 轻微差异；
- few-pixel positional difference；
- complex ornamentation 不完全一致；
- 小幅圆角 / stroke 渲染差异。

---

# 16. Performance & Efficiency Tests

v2.0 不设置：

```text
Total Runtime <= N minutes
```

作为硬 SLA。

测试重点是：

> 是否存在无质量收益的重复执行。

## PERF-01 Environment Failure Before Planner

期望：

```text
Preflight fail
→ Planner calls = 0
```

## PERF-02 Render Failure

期望：

```text
Render technical failure
→ additional Planner calls = 0
```

## PERF-03 Reviewer Timeout

期望：

```text
additional Planner calls = 0
```

## PERF-04 Local Patch

期望：

```text
local connector issue
→ Full Replan = 0
```

## PERF-05 Stage Reuse

期望：

```text
unchanged passed stage
→ reused = true
```

## PERF-06 Zero Asset

期望：

```text
asset pipeline unnecessary stages skipped
```

---

# 17. Performance Evidence

每个 Baseline 与关键 E2E 应记录：

```text
total duration
preflight duration
planner duration
validation duration
asset duration
build duration
render duration
qa duration
reviewer duration
planner call count
reviewer call count
technical retry count
visual revision count
full replan count
```

第一版用于：

- 回归比较；
- 发现异常；
- 定位瓶颈。

不是固定时间 Release Gate。

---

# 18. Content-to-PPT E2E Test Sets

正式至少准备三套 Deck。

## D03 — 3 页 Small Deck

目标：

> 快速完整 E2E。

覆盖：

```text
materials
→ outline
→ confirmation
→ wireframe
→ design
→ reconstruction
→ reviewer
→ assembly
```

用于日常 Smoke E2E。

---

## D05 — 5 页 Threshold Deck

验证：

```text
≤ 5 pages
→ default full design
```

重点：

- 不自动进入 Sample-first；
- 全部页面正常生成；
- Deck Assembly 正确。

---

## D08/D10 — 8–10 页 Multi-slide Deck

验证：

```text
> 5 pages
→ representative sample strategy
```

同时验证：

- deck_state；
- limited parallelism；
- slide isolation；
- page order；
- failure isolation；
- Deck Assembly；
- Deck QA。

8–10 页中具体页数可由固定测试样本确定，但一旦选定应保持稳定。

---

# 19. Outline Acceptance Tests

## OUT-01 Required Confirmation

正式 Content-to-PPT：

```text
Candidate Outline
→ User Confirmation
→ Approved Outline
```

用户未确认时，不得进入正式全量下游生成。

Blocking。

## OUT-02 Content Freeze

Approved Outline / Slide Content 后，下游不得擅自改写。

Blocking。

## OUT-03 User Revision

用户修改确认内容后：

```text
new revision
```

而不是静默覆盖。

Blocking。

---

# 20. Wireframe Tests

## WF-01 Valid Spec

每页 Wireframe Spec：

- 合法；
- 内容区域完整；
- bbox 不越界；
- page size 一致。

## WF-02 SVG Render

```text
Wireframe Spec
→ SVG
```

可稳定渲染。

## WF-03 Content Integrity

Wireframe 规划不得改写 Approved Slide Content。

以上均为 Blocking。

---

# 21. Visual Design Tests

## VD-01 Design Image Exists

每个需设计页面产生 Design Image。

## VD-02 Text Authority

Design Image 即使产生错字，后续 PPT 仍使用 Approved Slide Content。

## VD-03 Visual Authority

Layout Planner 不得擅自重新设计与 Design Image 明显不同的页面。

## VD-04 Five-page Strategy

5 页 Deck 默认全量设计。

## VD-05 Long-deck Strategy

>5 页默认走 Sample-first 策略。

## VD-06 User Override

用户明确要求直接全部生成时，Host 能覆盖默认 Sample 策略。

---

# 22. Multi-slide Isolation Tests

## MS-01 run_state Isolation

每页拥有独立 run_state。

slide-03 状态更新不得覆盖 slide-04。

## MS-02 Artifact Isolation

每页：

- spec；
- assets；
- render；
- QA；
- Reviewer Result；

不得串页。

## MS-03 Reviewer Issue Isolation

slide-03 Reviewer Issue 不得 Patch slide-04。

## MS-04 Failure Isolation

slide-03 failed：

> 不得自动中止所有独立页面。

## MS-05 Ordering

并行执行后最终：

```text
slide order
=
Approved Outline order
```

以上均为 Blocking。

---

# 23. Limited Parallelism Tests

测试：

- 串行；
- 有限并发。

检查：

```text
same input
→ equivalent content / slide order / state correctness
```

不要求 Render 像素完全一致。

特别测试 PowerPoint COM：

> 如果并发 Office Automation 不稳定，允许通过串行 COM Worker / Lock 实现稳定执行。

Release Gate 关注：

```text
correctness
>
maximum concurrency
```

---

# 24. Deck Assembly Tests

## DA-01 Slide Count

输入 N 页：

```text
final deck slide count = N
```

Blocking。

## DA-02 Slide Order

顺序与 deck_state / Approved Outline 一致。

Blocking。

## DA-03 Openability

Final PPTX 能由 Microsoft PowerPoint 正常打开。

Blocking。

## DA-04 Saveability

打开后能够正常保存。

Blocking。

## DA-05 Editability Retention

合并后：

- 主要文字仍可编辑；
- 主要结构未被整页 rasterize。

Blocking。

## DA-06 No Blank / Lost Slides

不存在意外空白页、丢页、重复页。

Blocking。

---

# 25. Deck QA Tests

至少验证：

```text
slide count
slide order
page dimensions
file integrity
blank slides
duplicate slides
missing slides
assembly status
per-slide status consistency
```

Deck QA 为 deterministic Gate。

---

# 26. State Tests

## ST-01 run_state

单页详细状态权威。

## ST-02 deck_state

只保存 Deck 汇总和编排状态。

## ST-03 runtime-manifest

只保存 Runtime 环境状态。

正式断言：

```text
runtime-manifest
≠
run_state
≠
deck_state
```

## ST-04 Resume Identity

State 必须能够定位当前 resume 起点。

## ST-05 Retry Counters

以下计数器独立：

```text
technical_retry_count
visual_revision_count
full_semantic_replan_count
```

不能互相覆盖。

以上均为 Blocking。

---

# 27. Artifact Authority Tests

## ART-01 Content Conflict

Approved Slide Content 与 Design Image OCR 不一致。

正式结果必须使用 Approved Content。

## ART-02 Visual Conflict

Design Image 与 Planner 自行设计不同。

Planner 应按照 Design Image。

## ART-03 PPT Actual Structure

Spec 声称存在对象但 PPTX 中不存在。

Actual PPTX / OOXML 为当前实际结构判断依据。

## ART-04 Render Truth

Planner 声称视觉正确但实际 Render 错误。

以 Render 为实际视觉结果。

## ART-05 Cache Is Not Truth

删除 cache：

> 正式 Artifact 和权威内容不得丢失。

---

# 28. Clean Install Acceptance

Release Candidate 必须执行。

## CI-01 Installation

```text
install.ps1
```

在干净 Windows 环境成功运行。

## CI-02 Managed Runtime

建立项目受控 Runtime。

## CI-03 Python Dependencies

无需用户手工寻找多个 Python 环境。

## CI-04 Node Dependencies

无需依赖用户全局 npm 包。

## CI-05 PowerPoint Detection

正确检测 Microsoft PowerPoint。

## CI-06 COM Verification

PowerPoint COM Smoke Test 成功。

## CI-07 First Real Task

首次真实图片转 PPT 成功。

## CI-08 Content-to-PPT

至少一套小型 Content-to-PPT 成功。

任一失败：

```text
Release = BLOCKED
```

---

# 29. Claude Code E2E Acceptance

至少验证：

- Skill 可被发现 / 使用；
- Task Routing 正确；
- references 按需使用；
- Outline 流程正确；
- Runtime Ready Gate 正确；
- Layout Planner 调度正确；
- Reviewer 调度正确；
- Delivery Gate 正确；
- Final PPTX 正常。

Blocking。

---

# 30. Codex E2E Acceptance

与 Claude Code 对应验证同一类核心能力。

不要求自然语言结果完全一致。

要求：

> 两者均能遵守同一 Skill Contract。

Blocking。

---

# 31. Regression Test

## 31.1 Image-to-Editable-PPT

v2.0 不能破坏旧入口。

每次关键阶段完成后至少跑固定 Baseline。

## 31.2 Baseline Regression

重点比较：

- 可编辑性；
- 内容完整性；
- Major / Critical；
- Planner 调用；
- Reviewer 调用；
- Technical Retry；
- Stage Reuse；
- Runtime failure behavior。

## 31.3 不要求 Pixel-perfect Golden

除非某个确定性渲染测试专门要求。

---

# 32. Release Failure 分级

正式采用：

```text
Blocking
Warning
Deferred
```

---

# 33. Blocking

以下任一问题出现即阻止正式 Release。

## Content

- Approved Content 被下游改写；
- 页面主要内容缺失；
- Source Slide Content 冻结失效。

## Editability

- 主要文字不可编辑；
- 整页 rasterization 规避。

## Runtime

- Clean Install 失败；
- Bootstrap 失败；
- Preflight 无效；
- Runtime Repair 无限循环；
- Technical Retry 超过 2 次。

## Recovery

- 技术错误触发无意义 Planner；
- Reviewer timeout 触发 Replan；
- Local Issue 触发不必要 Full Replan；
- Resume 无法复用已通过阶段。

## Visual

- 未解决 Critical；
- 未解决 Major。

## Deck

- slide count 错误；
- page order 错误；
- page state 串页；
- Reviewer Issue 串页；
- 丢页；
- 重复页；
- Final PPTX 无法打开。

## Host

- Claude Code 核心 E2E 失败；
- Codex 核心 E2E 失败。

## Backward Compatibility

- Image-to-Editable-PPT 固定 Baseline 出现实质退化。

---

# 34. Warning

不阻塞 Release，但必须记录。

例如：

- Reviewer 偶发技术超时，但降级逻辑正确；
- Minor 视觉差异；
- 非关键诊断字段缺失；
- 总耗时轻微波动；
- 某个非关键日志显示不完整。

Warning 不得用于掩盖 Blocking 问题。

---

# 35. Deferred

明确不属于 v2.0 当前范围。

包括：

- macOS；
- Linux；
- LibreOffice；
- 其他 Office Backend；
- 50 页以上压力测试；
- Deck-level AI Reviewer；
- Visual Designer Agent；
- Outline Planner Agent；
- Wireframe Planner Agent；
- 跨平台视觉 parity。

Deferred 项失败：

> 不影响 v2.0 Release。

---

# 36. P0 Gate

P0 完成标准：

- 6 个固定 Baseline 已选定；
- 所有输入已保存；
- 当前输出已保存；
- 当前 Planner / Reviewer 调用已记录；
- 当前 Render / QA 已保存；
- timing 已记录；
- baseline report 完整。

未完成：

```text
不得进入正式 Runtime Hardening 验收。
```

---

# 37. P0.5 Gate — Runtime Hardening

必须通过：

- Clean Runtime readiness；
- Shared Validator；
- Technical Retry；
- Retry limit = 2；
- Targeted Patch；
- Resume；
- Stage Reuse；
- Zero-Asset Fast Path；
- Reviewer technical degradation；
- content authority protection；
- old baseline regression。

P0.5 是 v2.0 最重要的技术 Gate。

---

# 38. P1 Gate — Content Planning

必须通过：

- Content-to-PPT routing；
- material understanding；
- candidate outline；
- mandatory user outline confirmation；
- Approved Outline；
- Approved Slide Content；
- revision / freeze rules；
- Image-to-PPT 不被错误路由到 Outline。

---

# 39. P2 Gate — Wireframe

必须通过：

- Wireframe Spec；
- SVG Render；
- content integrity；
- user-visible / internal-only 两种模式；
- page-by-page validity。

---

# 40. P3 Gate — Visual Design

必须通过：

- Visual Design Brief；
- Design Image generation；
- content authority；
- visual source-of-truth；
- 5 页边界策略；
- >5 页 Sample Strategy；
- user override。

---

# 41. P4 Gate — Deck Orchestration

必须通过：

- per-slide workspace；
- run_state isolation；
- deck_state；
- limited parallelism；
- page order；
- issue isolation；
- failure isolation；
- equivalent serial / limited-parallel correctness。

---

# 42. P5 Gate — Deck Assembly & QA

必须通过：

- PowerPoint COM Assembly；
- slide count；
- slide order；
- no blank / lost slides；
- final PPT openability；
- saveability；
- editability retention；
- Deck QA。

---

# 43. P6 Gate — Release

必须通过：

```text
P0–P5
+
Claude Code E2E
+
Codex E2E
+
Clean Windows E2E
+
Image-to-Editable-PPT Regression
+
Content-to-PPT 3 / 5 / 8–10 page E2E
```

且：

```text
Blocking Issues = 0
```

Warning 可以存在，但必须登记。

Deferred 不影响 Release。

---

# 44. Test Evidence

每个正式测试至少记录：

```text
test_id
date
environment
skill_version / commit
input artifacts
expected behavior
actual behavior
pass / fail
blocking level
evidence paths
notes
```

Agent / Visual 测试额外保存：

- model / agent identifier；
- input contract；
- output；
- Reviewer Result；
- relevant Render。

---

# 45. Test Report

每个阶段建议生成：

```text
P0_baseline_report
P0_5_runtime_hardening_report
P1_content_planning_report
P2_wireframe_report
P3_visual_design_report
P4_deck_orchestration_report
P5_deck_assembly_report
P6_release_report
```

具体格式后续实现时确定。

---

# 46. 自动化优先级

优先自动化：

1. schema；
2. validator；
3. content equality；
4. state；
5. retry count；
6. stage reuse；
7. file existence；
8. PPT openability；
9. slide count；
10. slide order；
11. run_state / deck_state；
12. artifact identity。

视觉和生成式 Agent 测试：

> 允许结构化人工 / Reviewer 辅助验收，不强求全部转为机械断言。

---

# 47. 不能被测试替代的用户确认

测试系统不能模拟掉正式业务规则。

例如 Content-to-PPT：

```text
Approved Outline
```

必须来自实际用户确认或测试夹具中显式模拟的“confirmed state”。

不得让测试为了方便把：

```text
Candidate Outline
```

直接当作：

```text
Approved Outline
```

而不记录确认状态。

---

# 48. 版本回归原则

每次影响以下模块时必须至少跑对应 Baseline：

| 修改模块 | 最低回归范围 |
|---|---|
| Planner | B01–B06 |
| Validator | B01–B06 + validator tests |
| Builder | B01–B06 |
| Render | B01–B06 render tests |
| Reviewer | B01–B06 reviewer tests |
| Runtime Recovery | FR 系列 |
| Artifact / State | ST + ART 系列 |
| Deck Orchestrator | D03 + D05 |
| Deck Assembly | D03 + DA 系列 |
| Host Rules | 至少一套 Host E2E |

---

# 49. Release Checklist

正式 v2.0 Release Candidate 必须满足：

```text
[ ] Windows 11 x64 reference environment tested
[ ] Microsoft PowerPoint COM verified
[ ] Clean Windows installation passed
[ ] 6 baseline slides frozen and regressed
[ ] technical retry max = 2 verified
[ ] no technical failure causes semantic replan
[ ] Stage Reuse verified
[ ] Zero-Asset Fast Path verified
[ ] content authority verified
[ ] Visual Critical = 0
[ ] Visual Major = 0
[ ] 3-page E2E passed
[ ] 5-page boundary E2E passed
[ ] 8–10 page Deck E2E passed
[ ] multi-slide isolation passed
[ ] Deck Assembly passed
[ ] Deck QA passed
[ ] Claude Code E2E passed
[ ] Codex E2E passed
[ ] Image-to-Editable-PPT regression passed
[ ] Blocking issues = 0
[ ] Warnings documented
[ ] Deferred items documented
```

---

# 50. 最终验收原则

`Content to Editable PPT Skill` v2.0 的测试与验收原则可以概括为：

> 使用 Windows 11 x64 + Microsoft PowerPoint 作为唯一正式参考环境，通过固定 6 个 Single-Slide Baseline、3 / 5 / 8–10 页三档 Deck E2E、Claude Code 与 Codex 双 Host 端到端测试和至少一次 Clean Windows 安装测试，证明 Skill 不仅“代码可运行”，而且能够稳定安装、正确执行、保持内容权威、维持主要可编辑性、完成视觉审核、限制无效 Agent 重试、支持 Targeted Patch 与 Resume，并正确组装最终 PowerPoint。确定性组件采用严格断言，生成式 Agent 采用契约型验收；视觉 Gate 要求 Critical 和 Major 均为 0；不设置任意总时间 SLA，而以减少无质量收益的重复执行作为性能核心指标。所有 Release 问题按 Blocking、Warning 和 Deferred 分类，正式发布要求 Blocking Issues = 0。
