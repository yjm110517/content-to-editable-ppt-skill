# Content to Editable PPT Skill Artifact、State 与权威数据契约 v1.0

> 中文名：Content to Editable PPT Skill 产物、状态与权威数据契约 v1.0  
> 英文名：Artifact, State & Source-of-Truth Contract v1.0

## 1. 文档目的

本文档定义 `Content to Editable PPT Skill` 在整个生成、重建、审核和交付流程中：

- 会产生哪些 Artifact；
- 哪些数据属于运行 State；
- 哪些数据属于权威来源；
- 不同 Artifact 之间如何建立依赖关系；
- 谁可以生成、读取、修改或覆盖某类数据；
- 当数据冲突时以谁为准；
- 某一 Artifact 发生变化后，哪些下游结果必须失效；
- 哪些结果可以继续复用；
- 哪些 Artifact 面向用户交付，哪些仅作为内部运行数据。

本文档的核心目标是：

> 防止内容权威漂移、状态混乱、重复 OCR、无边界覆盖和无意义全量重跑，为 Resume、Stage Reuse、Targeted Patch、多页并行和内容冻结提供统一的数据契约。

本文档不定义：

- 具体目录结构；
- 最终文件名；
- JSON Schema 的全部字段；
- hash 算法；
- 数据库存储；
- 单页 Runtime 的完整执行顺序；
- Agent Prompt；
- Deck 合并技术实现。

上述内容由后续架构设计、Schema Design 和 Runtime 实现文档定义。

---

# 2. 核心原则

第一版冻结以下原则：

1. **内容权威与视觉权威分离；**
2. **Approved / Source Slide Content 是文字权威源；**
3. **Design Image 是页面视觉权威源；**
4. **Design Image OCR 不得覆盖已冻结文字；**
5. **Image-to-Editable-PPT 在正式重建前必须形成并冻结 Source Slide Content；**
6. **单页详细状态与 Deck 汇总状态分离；**
7. **runtime-manifest 与任务 State 完全分离；**
8. **Artifact 失效按依赖关系向下传播，不默认全量失效；**
9. **权威内容 Artifact 不允许静默覆盖，变更应形成新 revision；**
10. **内部技术 Artifact 默认不作为用户交付物。**

---

# 3. Artifact 定义

Artifact 指：

> 在 Skill 工作流中，被某一阶段正式生成、供后续阶段读取、验证、修改、缓存、交付或用于状态恢复的结构化产物。

Artifact 可以是：

- 文本；
- JSON / YAML；
- 图片；
- PPTX；
- Render；
- QA 结果；
- Reviewer Issue；
- Patch；
- Manifest；
- 其他结构化中间结果。

Artifact 不等同于临时文件。

只有被正式纳入流程依赖关系的产物才属于受本契约管理的 Artifact。

---

# 4. State 定义

State 指：

> 描述当前运行流程“进行到哪里、当前状态是什么、哪些阶段已完成、哪些阶段失败、哪些阶段可恢复”的控制数据。

State 不用于保存页面正文、设计图、重建规格等业务 Artifact 本体。

State 的职责是：

- 支持 Resume；
- 支持 Stage Reuse；
- 支持 Retry；
- 支持 Failure Recovery；
- 支持多页编排；
- 支持可观测性。

---

# 5. 权威数据定义

“权威数据”指：

> 当同一事实在多个 Artifact 中出现不一致时，用于判定正确值的 Source of Truth。

不同维度允许存在不同权威源。

例如：

```text
文字真值
→ Approved / Source Slide Content

视觉目标
→ Design Image

实际 PPT 结构
→ PPTX / OOXML

实际视觉结果
→ Render Image

视觉质量判断
→ Visual Reviewer Result
```

因此：

> 不存在一个 Artifact 对所有维度拥有绝对权威。

---

# 6. 第一版核心 Artifact 清单

| Artifact | 主要作用 | 典型生产者 | 是否权威 |
|---|---|---|---|
| User Source Materials | 用户原始材料 | User | 原始输入权威 |
| Approved Outline | 用户确认的 Deck 内容结构 | Host + User | Deck 内容结构权威 |
| Approved Slide Content | Content-to-PPT 单页确认文字 | Host + User | 单页文字权威 |
| Source Slide Content | 图片直转场景中冻结后的可见文字 | Host / Vision | 单页文字权威 |
| Wireframe Spec | 页面信息结构与空间规划 | Host | 布局规划依据 |
| Wireframe Preview | Wireframe 可视化结果 | Runtime / Renderer | 非权威预览 |
| Design Image | 页面最终视觉设计目标 | Host / Image Generation | 页面视觉权威 |
| Reconstruction Spec | 可编辑 PPT 重建执行规格 | Layout Planner | 构建规格权威 |
| Processed Assets | 处理后的页面资产 | Runtime | 资产执行产物 |
| PPTX | 实际构建的 PowerPoint 页面 / 文件 | Runtime | 实际结构产物 |
| Render Image | PowerPoint / Backend 实际渲染结果 | Runtime | 实际视觉结果 |
| Structural QA Result | 结构与可编辑性检查结果 | Runtime | 结构 QA 判断依据 |
| Visual Reviewer Result | 独立视觉审核结果 | Visual Reviewer | 视觉审核判断依据 |
| Reviewer Issues | 结构化视觉问题 | Visual Reviewer | 修订依据 |
| Targeted Patch | 对 Reconstruction Spec 的局部修改 | Layout Planner | 当前 Patch 执行依据 |
| run_state | 单页执行状态 | Runtime | 单页状态权威 |
| deck_state | Deck 汇总与编排状态 | Host / Runtime | Deck 状态权威 |
| runtime-manifest | Skill Runtime 环境状态 | Runtime | 环境状态权威 |
| Conversion Summary | 用户可读摘要 | Host / Runtime | 派生信息，不是控制权威 |
| Logs / Diagnostics | 调试与诊断信息 | Runtime / Agents | 非权威诊断数据 |

---

# 7. 内容权威源

## 7.1 Content-to-PPT

正式冻结：

```text
Approved Slide Content
= 单页文字唯一权威源
```

后续以下来源不得覆盖它：

- Design Image OCR；
- Layout Planner Vision；
- Render OCR；
- Reviewer OCR；
- Builder 推测；
- 模型语言优化。

如果：

```text
Approved Slide Content：
人工智能支持学习
```

而：

```text
Design Image：
人工只能支持学习
```

最终 PPT 必须使用：

```text
人工智能支持学习
```

## 7.2 Image-to-Editable-PPT

用户直接提供页面图片时：

```text
User Image
↓
Host / Vision
↓
Source Slide Content
↓
Freeze
```

正式重建开始后：

```text
Source Slide Content
= 单页文字唯一权威源
```

后续不得反复 OCR 并改变文字。

---

# 8. Source Slide Content 冻结规则

## 8.1 目的

避免：

```text
第一次OCR
→ 文本A

Planner再次OCR
→ 文本B

Reviewer再次OCR
→ 文本C
```

导致正文漂移。

## 8.2 冻结时点

Image-to-Editable-PPT 中：

> Source Slide Content 应在正式 Layout Planner Initial 之前形成。

## 8.3 不确定内容

如果图片中文字：

- 模糊；
- 被遮挡；
- 无法可靠判断；
- 存在多种可能；

应在冻结前由 Host 处理。

正式进入 Runtime 后，不应由 Layout Planner、Builder 或 Reviewer自行猜测。

---

# 9. 视觉权威源

第一版冻结：

```text
Design Image
= 页面视觉权威源
```

它定义：

- 页面总体构图；
- 主要区域比例；
- 视觉层级；
- 元素相对关系；
- 图像位置；
- 卡片形态；
- 色彩关系；
- 空间组织；
- 设计风格。

Layout Planner 的职责是：

> 尽可能将该视觉目标转换成可编辑 PowerPoint 对象。

Layout Planner 不得：

- 因自己认为另一种版式更好看而重新设计；
- 擅自改变视觉结构；
- 用自己的审美覆盖用户已确认设计。

---

# 10. Design Image 的权威边界

Design Image 是：

```text
视觉权威
```

但不是：

```text
文字权威
```

因此出现冲突时：

### 文字冲突

```text
Approved / Source Slide Content
>
Design Image OCR
```

### 视觉冲突

```text
Design Image
>
Layout Planner 自行设计判断
```

### 实际视觉判断

```text
Render Image
= 当前 PPT 实际呈现
```

Reviewer 应比较：

```text
Design Image
vs
Render Image
```

而不是比较：

```text
Reconstruction Spec
vs
Planner 自己的描述
```

---

# 11. Reconstruction Spec 权威范围

`Reconstruction Spec` 是：

> 当前 PPT Build 阶段的执行规格权威。

它可以定义：

- 元素类型；
- bbox；
- z-order；
- font；
- fill；
- stroke；
- asset reference；
- connector；
- editable / raster strategy。

但它不得覆盖：

```text
Approved / Source Slide Content
```

如果 Reconstruction Spec 中的 text 与权威内容冲突：

> Spec 必须被判为无效或修正，而不是反向修改权威内容。

---

# 12. PPTX 与 Render 的权威范围

## 12.1 PPTX

PPTX 是：

> 实际构建结构的最终实体。

用于验证：

- 原生文本；
- 原生形状；
- OOXML；
- 资产关系；
- 页面对象；
- 编辑性。

## 12.2 Render Image

Render Image 是：

> 当前 PPT 在实际 Office / Render Backend 中的视觉结果。

因此：

```text
Planner 声称已还原
≠
实际视觉已经还原
```

真正视觉审核必须基于 Render。

---

# 13. Structural QA 与 Visual Reviewer 的权威范围

## 13.1 Structural QA Result

负责判断：

- PPTX 是否正常；
- 内容是否完整；
- 主要文字是否 native editable；
- 页面是否异常栅格化；
- 对象是否缺失；
- OOXML / Font / Asset 是否存在明显问题。

## 13.2 Visual Reviewer Result

负责判断：

- 页面是否视觉还原；
- 是否存在 Major / Critical 视觉问题；
- connector；
- crop；
- hierarchy；
- alignment；
- proportions；
- style drift；
- background seam 等。

Visual Reviewer 不负责改写内容。

---

# 14. 权威来源优先关系

不同维度的正式优先关系如下。

## 14.1 用户意图

```text
用户最新明确指令
>
旧版本要求
```

## 14.2 Deck 内容结构

```text
Approved Outline
>
候选 Outline
>
模型早期规划
```

## 14.3 页面文字

Content-to-PPT：

```text
Approved Slide Content
>
Design Image OCR
>
Planner Vision Guess
```

Image-to-Editable-PPT：

```text
Source Slide Content
>
Planner / Reviewer OCR
```

## 14.4 页面视觉目标

```text
Design Image
>
Wireframe Preview
>
Planner 自行审美调整
```

## 14.5 实际结构

```text
PPTX / OOXML
>
Reconstruction Spec 声明
```

## 14.6 实际视觉

```text
Render Image
>
Builder / Planner 声称
```

## 14.7 视觉审核

```text
Visual Reviewer Result
```

负责最终独立视觉判断，但不拥有最终 Delivery 权。

---

# 15. Artifact 写权限

| Artifact | Host | Layout Planner | Visual Reviewer | Runtime |
|---|---:|---:|---:|---:|
| User Source Materials | 只读 | 只读（按需） | ❌ | 只读 |
| Approved Outline | ✅确认前修改 | ❌ | ❌ | 只读 |
| Approved Slide Content | ✅确认前 / 用户重新确认 | 只读 | 只读 | 只读 |
| Source Slide Content | ✅冻结前 | 只读 | 只读 | 只读 |
| Wireframe Spec | ✅ | ❌ | ❌ | 读取 / 渲染 |
| Design Image | ✅生成 / 更新 | 只读 | 只读 | 只读 |
| Reconstruction Spec | 调度 / 读取 | ✅ | 只读 | 读取 |
| Processed Assets | 调度 / 读取 | 只读 | 只读 | ✅ |
| PPTX | 读取 / 交付 | ❌ | 只读 | ✅ |
| Render Image | 读取 | ❌ | 只读 | ✅ |
| Structural QA Result | 读取 | 读取摘要 | 读取摘要 | ✅ |
| Visual Reviewer Result | 读取 / 路由 | 读取 Issue | ✅ | 读取 |
| Targeted Patch | 调度 | ✅ | ❌ | ✅执行 |
| run_state | 读取 / 调度 | ❌ | ❌ | ✅ |
| deck_state | ✅调度 / 汇总 | ❌ | ❌ | ✅更新技术状态 |
| runtime-manifest | 读取 | ❌ | ❌ | ✅ |
| Conversion Summary | ✅ | ❌ | ❌ | 可派生 |
| Logs | 读取 | 可产生日志 | 可产生日志 | ✅ |

---

# 16. 权威内容的不可静默覆盖原则

## 16.1 Approved Outline

一旦用户确认：

```text
Approved Outline v1
```

不得通过内部 Agent 静默改写。

如用户后续明确修改，应形成：

```text
Approved Outline v2
```

或等价 revision。

## 16.2 Approved Slide Content

同理：

```text
Approved Slide Content v1
```

如果用户重新确认文本：

```text
Approved Slide Content v2
```

不得只是无记录覆盖。

## 16.3 Source Slide Content

Image-to-Editable-PPT 中一旦冻结，后续识别修改也必须产生新的 revision。

---

# 17. Revision 原则

第一版只冻结逻辑，不冻结具体文件名。

每个关键权威 Artifact 应至少能够逻辑上表示：

- artifact id；
- revision；
- parent revision；
- created_at；
- source / parent reference；
- hash 或等价内容标识。

实现可以选择：

```text
slide_content_v1.json
slide_content_v2.json
```

也可以采用其他版本存储方式。

但必须能够回答：

> 当前 PPT 是根据哪一个版本的内容和设计图生成的。

---

# 18. 单页 State

每一页应拥有独立详细：

```text
run_state
```

run_state 用于记录：

- slide id；
- current stage；
- stage status；
- Layout Planner call count；
- Full Semantic Replan count；
- Targeted Revision count；
- Technical Retry count；
- current Reconstruction Spec revision；
- Design Image revision；
- Content revision；
- Build status；
- Render status；
- Structural QA status；
- Reviewer status；
- Delivery status；
- Last failure classification；
- 可复用 Artifact 引用。

具体字段后续定义。

---

# 19. Deck State

多页任务应有一个轻量：

```text
deck_state
```

负责：

- Deck id；
- 页面列表；
- 页面顺序；
- 每页总体状态；
- 页面是否 ready for assembly；
- Deck assembly status；
- Deck QA status；
- final delivery status。

例如：

```text
slide-01 → delivered
slide-02 → reviewing
slide-03 → failed
assembly → pending
```

Deck State 不应保存：

- 每页完整 Planner 输出；
- 每页完整 Reviewer Issues；
- 每页全部日志；
- 每页详细技术阶段数据。

这些应留在单页 run_state 和对应 Artifact 中。

---

# 20. runtime-manifest

`runtime-manifest` 表示：

> Skill 运行环境本身是什么状态。

例如：

- OS；
- architecture；
- Python；
- Node；
- dependencies；
- PowerPoint；
- Office Backend；
- full_fidelity；
- verify status。

它与任务无关。

正式冻结：

```text
runtime-manifest
≠
run_state
≠
deck_state
```

三个状态域不得合并为同一个权威状态文件。

---

# 21. Artifact 依赖关系

基础依赖链可以理解为：

```text
User Source Materials
↓
Approved Outline
↓
Approved Slide Content
↓
Wireframe Spec
↓
Design Image
↓
Reconstruction Spec
↓
Processed Assets
↓
PPTX
↓
Render Image
↓
Structural QA
↓
Visual Reviewer Result
```

但实际失效规则应按“直接输入依赖”判断，而不是简单地认为所有上游修改都会让所有下游全部失效。

---

# 22. Dependency-based Invalidation

正式冻结：

> 谁的输入发生变化，谁以及依赖该输入的下游 Artifact 才失效。

不采用：

```text
任意Artifact变化
→ 所有结果全部删除
→ 从头开始
```

---

# 23. Approved Slide Content 变化后的失效规则

如果用户重新确认页面正文：

```text
Approved Slide Content v1
→ v2
```

至少以下 Artifact 需要重新判定：

```text
Wireframe Spec
Design Image
Reconstruction Spec
PPTX
Render Image
Structural QA
Visual Reviewer Result
```

其中：

- 若 Host 判断布局结构仍适用，Wireframe 可以被重新验证而非必然重做；
- Design Image 若仍含旧文字，则必须更新；
- Reconstruction Spec 必须重新基于新内容验证；
- PPTX 及其所有下游必须失效。

原则：

> 内容变化不能继续复用包含旧内容的 PPTX / Render / Reviewer Result。

---

# 24. Design Image 变化后的失效规则

若：

```text
Approved Slide Content 不变
Design Image v1 → v2
```

则：

```text
Approved Slide Content   保留
Wireframe                可保留
Design Image             更新
Reconstruction Spec      失效
PPTX                     失效
Render                    失效
Structural QA            失效
Reviewer Result          失效
```

---

# 25. Reconstruction Spec 局部 Patch 后的失效规则

例如：

```text
connector endpoint
bbox
font size
fill
stroke
z-order
```

发生局部 Patch：

```text
Approved Content       保留
Design Image           保留
无关 Assets            保留
Reconstruction Spec    局部新 revision
PPTX                   失效
Render                 失效
Structural QA          失效
Reviewer Result        失效
```

如果 Patch 不涉及 Asset Processing：

> 已处理资产继续复用。

---

# 26. Asset 变化后的失效规则

## 26.1 Crop 参数变化

失效：

- 对应 Processed Asset；
- PPTX；
- Render；
- QA；
- Reviewer Result。

其他无关资产保持有效。

## 26.2 新增 / 删除资产

对应依赖该资产的 Reconstruction Spec 部分和下游结果失效。

不得无理由使全部页面资产失效。

---

# 27. Render 或 Reviewer 技术失败

如果：

```text
PPTX 未变化
Render 工具技术失败
```

则：

```text
Reconstruction Spec  保留
Processed Assets     保留
PPTX                 保留
```

只需从：

```text
Render
```

恢复。

如果 Reviewer 技术失败：

```text
Design Image       保留
PPTX               保留
Render             保留
Structural QA      保留
```

只需：

```text
Reviewer retry
```

或按规则进入 Warning Gate。

---

# 28. Artifact Hash / Input Identity

为了支持 Stage Reuse，每个重要 Artifact 应有稳定的：

```text
content identity
```

可以通过：

- hash；
- version；
- artifact id + revision；

等方式实现。

Stage 应能够判断：

```text
输入是否变化？
```

若：

```text
输入 identity 未变化
+
上一结果 passed
```

则：

```text
reuse
```

具体 hash 算法后续定义。

---

# 29. Artifact 生命周期状态

每个 Artifact 可逻辑上拥有：

```text
created
validated
active
superseded
invalidated
archived
```

第一版无需全部物理实现，但必须能够区分：

### active

当前正式使用版本。

### superseded

被新 revision 替代，但保留追踪关系。

### invalidated

由于上游依赖变化，不可继续用于当前执行。

---

# 30. Artifact 与缓存的关系

Artifact 是正式流程数据。

Cache 是：

> 为提高运行效率而保存的可复用副本或派生结果。

因此：

```text
cache
≠
source of truth
```

如果 Cache 与正式 Artifact 冲突：

> 正式 Artifact 优先。

Cache 可以被删除并重新生成，不得影响内容权威。

---

# 31. Logs 与诊断信息

Logs 只用于：

- debugging；
- timing；
- error diagnosis；
- call tracing；
- performance analysis。

Logs 不应被用作：

- Approved Content；
- Design Truth；
- Run State；
- Runtime Manifest；
- Delivery status；

的唯一权威来源。

---

# 32. Conversion Summary

`Conversion Summary` 是：

> 面向用户或开发者的派生摘要。

可能包含：

- 页面状态；
- Reviewer 是否完成；
- Warning；
- Backend；
- 是否 Full Fidelity；
- Revision 次数。

但：

```text
Conversion Summary
```

不是状态控制文件。

不得通过修改 Summary 反向改变：

```text
run_state
```

或 Delivery Gate。

---

# 33. 用户默认交付 Artifact

普通 Content-to-PPT 用户默认交付：

```text
1. Confirmed Outline
2. Design Images
3. Final Editable PPTX
```

必要时附加：

```text
Conversion / Warning Summary
```

---

# 34. 默认内部 Artifact

以下默认作为内部数据保存，不主动向普通用户交付：

- Reconstruction Spec；
- Processed Assets；
- run_state；
- deck_state；
- runtime-manifest；
- Structural QA raw result；
- Reviewer raw result；
- Reviewer Issues；
- Targeted Patch；
- Logs；
- Cache；
- Validator diagnostics。

如果用户、开发者或调试任务明确要求，可以输出。

---

# 35. 多页隔离

每一页必须有独立：

- Approved / Source Slide Content；
- Design Image；
- Reconstruction Spec；
- Processed Assets；
- PPTX / page output；
- Render；
- QA；
- Reviewer Result；
- Patch；
- run_state。

禁止：

```text
slide-03 Reviewer Issue
→ 修改 slide-04 Reconstruction Spec
```

除非存在明确的 Deck 级共享设计决策，并由 Host 显式路由。

---

# 36. 共享 Artifact

部分 Deck 级 Artifact 可以共享，例如：

- Approved Outline；
- Deck visual direction；
- theme / font policy；
- shared logo；
- shared brand assets；
- deck_state。

但共享 Artifact 发生变化时，应根据真实依赖关系决定哪些页面失效。

不能默认：

```text
一个共享Logo更新
→ 所有页面全部重新Planner
```

应只使真正使用该 Logo 的页面相应阶段失效。

---

# 37. 并发写入原则

多页并行时：

> 每页不得竞争写入同一个单页 Artifact 或 run_state。

Deck State 更新应避免：

- 页面状态互相覆盖；
- 页面顺序混乱；
- Reviewer Issue 归属错误；
- Patch 归属错误。

具体锁机制和并发实现后续架构阶段定义。

---

# 38. Delivery Status 权威

最终 Delivery Status 由：

```text
Host
+
Deterministic Delivery Gate
```

产生。

Reviewer 不能直接把：

```text
pass
```

写成：

```text
delivered
```

建议状态：

```text
delivered
delivered_with_warnings
revision_required
failed
```

其权威状态应写入：

- 单页 `run_state`；
- Deck 汇总状态 `deck_state`。

---

# 39. 冲突处理规则

## 39.1 内容冲突

```text
Approved / Source Slide Content
vs
Design Image OCR
```

使用前者。

## 39.2 视觉冲突

```text
Design Image
vs
Planner 重新设计
```

使用 Design Image。

## 39.3 Spec 与实际 PPT 冲突

```text
Reconstruction Spec
vs
PPTX / Render
```

实际 PPTX / Render 表示当前真实结果。

Spec 需要修正。

## 39.4 State 与日志冲突

```text
run_state
vs
log text
```

正式 run_state 是状态权威。

Log 仅用于诊断。

## 39.5 Runtime 状态冲突

```text
runtime-manifest
vs
旧任务状态
```

Runtime 当前验证结果优先决定环境是否可用。

---

# 40. 第一版数据修改矩阵

| 修改对象 | 是否允许原地静默覆盖 | 推荐行为 |
|---|---:|---|
| Approved Outline | ❌ | 新 revision |
| Approved Slide Content | ❌ | 新 revision |
| Source Slide Content | ❌ | 新 revision |
| Wireframe Spec | 可迭代 | 保留 revision / source |
| Design Image | 可迭代 | 新 revision |
| Reconstruction Spec | 可迭代 | Initial / Patch revision |
| Processed Asset | 可重建 | 根据输入 identity 生成 |
| PPTX | 可重建 | 新 Build output |
| Render | 可重建 | 由当前 PPTX 生成 |
| QA Result | 可重建 | 由当前 Build / Render 生成 |
| Reviewer Result | 可重建 | 绑定当前 Render |
| run_state | ✅ | 当前任务状态持续更新 |
| deck_state | ✅ | Deck 汇总持续更新 |
| runtime-manifest | ✅ | Runtime 验证后更新 |
| Logs | ✅追加 | 仅诊断 |

---

# 41. 第一版验收场景

至少验证以下数据行为。

## A01 内容与设计图文字冲突

```text
Approved Slide Content = A
Design Image OCR = B
```

最终 PPT 必须使用 A。

## A02 图片直转重复 OCR

正式重建后再次 OCR 得到不同文本。

系统必须继续使用冻结的 Source Slide Content。

## A03 Design Image 更新

内容不变、Design Image 更新。

要求：

```text
Content 保留
Spec / PPTX / Render / Review 失效
```

## A04 Connector Patch

只改变 connector。

要求：

```text
Content / Design / Assets 保留
Spec 局部 revision
PPTX 及下游失效
```

## A05 Render Technical Failure

PPTX 已通过 Build。

恢复时：

```text
PPTX 继续有效
从 Render 继续
```

## A06 Reviewer Technical Failure

QA 已通过。

不得使 Build / Render 失效。

## A07 Runtime Manifest 与 run_state 分离

Runtime 修复后：

- runtime-manifest 可以更新；
- 已完成任务 Artifact 不得因此自动删除；
- 单页 run_state 保持任务执行语义。

## A08 多页隔离

slide-03 发生 Patch。

slide-01、slide-02、slide-04 不得被无理由失效。

## A09 权威内容 Revision

用户确认新内容版本。

必须能够识别：

```text
current PPT
→ 基于哪个 content revision
```

## A10 Cache 删除

删除缓存后：

> 正式 Artifact 和权威内容不能因此丢失。

---

# 42. 第一版冻结关系

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
Reconstruction Spec
= 当前 Build 执行规格
```

```text
PPTX / OOXML
= 当前实际结构
```

```text
Render Image
= 当前实际视觉
```

```text
Structural QA
= 结构与可编辑性检查依据
```

```text
Visual Reviewer
= 独立视觉质量判断
```

```text
run_state
= 单页任务状态权威
```

```text
deck_state
= Deck 编排与汇总状态权威
```

```text
runtime-manifest
= Skill 运行环境状态权威
```

```text
Cache / Logs / Summary
≠ Source of Truth
```

---

# 43. 最终规范定义

`Content to Editable PPT Skill` v1.0 的 Artifact、State 与权威数据原则可以概括为：

> 整个 Skill 不使用单一“万能数据源”，而是根据不同信息维度建立明确的 Source of Truth：Approved / Source Slide Content 管文字，Design Image 管视觉目标，Reconstruction Spec 管构建执行，PPTX 与 Render 表示实际结果，QA 与 Visual Reviewer 分别负责结构和视觉判断。单页 run_state、Deck 状态和 Runtime Manifest 必须彼此分离。任何 Artifact 变化都按依赖关系向下失效，而不是默认全量重跑；权威内容不允许静默覆盖，后续变更必须可追踪。通过这一契约，为内容冻结、Targeted Patch、Resume、Stage Reuse、多页并行和最终交付提供一致的数据基础。
