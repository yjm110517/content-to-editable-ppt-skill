# Content to Editable PPT Skill 单页 Runtime 执行与错误恢复规范 v1.1

> 英文名：Single-Slide Runtime Execution & Error Recovery Specification v1.1

## v1.1 变更摘要

本版本同步总体架构 v2.0 的 Windows-only 决策，不改变单页 Runtime 的阶段边界、错误分类、Targeted Patch、Resume 或 Reviewer 降级交付规则。

主要变化：

- 只有 Windows、Microsoft PowerPoint Desktop 和 PowerPoint COM 全部 Ready 时才能进入 Layout Planner；
- 移除平台级 `degraded` 和 Compatible Backend 执行分支；
- 实际渲染统一使用 Microsoft PowerPoint COM；
- Reviewer 技术超时时的 `delivered_with_warnings` 仍作为审核降级路径保留。

## 1. 文档目的

本文档定义 `Content to Editable PPT Skill` 中单页图片转可编辑 PowerPoint Runtime 的正式执行流程、阶段边界、失败分类、技术重试、语义修订、定向 Patch、阶段复用、断点续跑、Visual Reviewer 调用、降级交付和最终状态判定规则。

本文档重点解决：

> 一张页面从“输入已准备完成”到“可编辑 PPT 页面交付”到底按什么顺序执行；发生错误后，应该重跑哪一部分，哪些情况禁止重新调用 Layout Planner，以及如何避免无意义的重复工作。

本文档适用于两种入口：

```text
Content-to-PPT
→ 页面设计图
→ Single-Slide Runtime
```

以及：

```text
Image-to-Editable-PPT
→ 用户直接提供页面图片
→ Single-Slide Runtime
```

本文档不定义：

- Skill 安装过程；
- Python / Node 依赖的具体安装方式；
- Runtime Bootstrap 目录结构；
- Layout Planner Prompt 具体内容；
- Visual Reviewer Prompt 具体内容；
- Reconstruction Spec 的最终 JSON Schema；
- Deck 合并实现；
- 多页任务的具体并发数。

上述内容分别由《运行环境安装与引导规范》《Agent 职责与交接契约》《Artifact、State 与权威数据契约》和后续详细设计文档定义。

---

# 2. Runtime 定位

Single-Slide Runtime 是：

> 将一张既定视觉页面转换为一页主要文字和主要结构可编辑的 PowerPoint，并完成结构检查、实际渲染、独立视觉审核和必要修订的单页执行链。

它不是：

- 内容大纲生成器；
- Wireframe 生成器；
- 页面视觉设计器；
- 通用图片编辑工具；
- Deck 总体设计器。

进入本 Runtime 时，页面的内容目标和视觉目标原则上已经确定。

---

# 3. 核心执行原则

Runtime 必须遵循以下原则：

1. **Runtime Ready 之后才允许调用 Layout Planner；**
2. **内容权威源与视觉权威源分离；**
3. **技术错误不得触发新的语义规划；**
4. **局部问题优先局部 Patch；**
5. **只有整体理解错误才允许 Full Replan；**
6. **已通过且输入未变化的阶段应尽量复用；**
7. **禁止无限重试；**
8. **Visual Reviewer 必须尝试调用；**
9. **Reviewer 技术不可用时允许满足条件的降级交付；**
10. **已确认内容不得被下游 Agent 改写；**
11. **不允许整页栅格图片冒充可编辑 PPT；**
12. **运行速度优化不得以取消必要质量 Gate 为代价。**

---

# 4. 正式输入

## 4.1 Content-to-PPT 页面输入

对于由完整 PPT 生成流程产生的页面，Single-Slide Runtime 至少接收：

### 1. Design Image

页面设计图。

作用：

> 定义这一页“应该长什么样”。

它是页面的视觉基准。

### 2. Approved Slide Content

已确认页面文字。

作用：

> 定义这一页“应该写什么”。

它是页面的文字权威源。

后续：

- Layout Planner；
- Builder；
- Reviewer；
- Patch；

都不得通过 OCR 或视觉识别覆盖 Approved Slide Content。

### 3. Related Assets

当前页面可使用的原始素材，例如：

- 图片；
- 图标；
- 插图；
- Logo；
- 背景视觉资产；
- 其他局部视觉素材。

### 4. Slide Specification

例如：

- 页面比例；
- 页面尺寸；
- 方向；
- 必要的页面级技术约束。

### 5. User Visual Constraints

用户已经确定的视觉要求，例如：

- 指定字体；
- 指定配色；
- 禁止改变的风格；
- 必须保留的视觉关系。

---

## 4.2 Image-to-Editable-PPT 页面输入

当用户直接提供一张 PPT 截图或设计图片时，不存在 Approved Outline。

在进入正式 Layout Planner 重建前，应先形成固定的：

```text
Source Slide Content
```

逻辑：

```text
User Image
↓
Host / Vision 提取可见文字
↓
形成 Source Slide Content
↓
冻结本次重建所使用的文字
↓
Single-Slide Runtime
```

之后：

> Source Slide Content 成为本次直接图片重建的文字基准。

后续不得在每个阶段重新 OCR 并改变文字。

若用户明确要求“严格按照图片中文字重建”，则 Source Slide Content 应尽可能忠实于原图。

若文字识别存在明显不确定性，应在进入正式重建前由 Host 处理，而不是在 Build 阶段临时猜测。

---

# 5. Runtime 前置 Gate

## 5.1 Fast Preflight

进入 Layout Planner 前必须执行：

```text
Fast Environment Preflight
```

Fast Preflight 由 Managed Runtime 提供。

至少确认：

- Runtime Manifest 有效；
- Skill 受控 Python 环境可用；
- 必要 Python 依赖可用；
- Node Runtime 可用；
- Node 项目依赖可用；
- Microsoft PowerPoint Desktop 可用；
- PowerPoint COM 已验证；
- 输出目录可写；
- 当前任务所需关键能力可用。

## 5.2 Runtime Ready

只有：

```text
runtime_status = ready
```

且 Windows、Microsoft PowerPoint Desktop 和 PowerPoint COM 全部验证通过时，才能进入 Layout Planner。

## 5.3 Preflight 失败

流程：

```text
Fast Preflight Fail
↓
Runtime Repair
↓
Reverify
├─ Pass → 继续
└─ Fail → environment_failure
```

Runtime Repair：

- 不消耗 Layout Planner 语义修订次数；
- 不消耗视觉修订次数；
- 不触发重新生成大纲；
- 不改变 Source / Approved Slide Content。

---

# 6. 标准 User Mode 执行流程

正式用户模式采用：

```text
Input Ready
↓
Fast Preflight
↓
Layout Planner Initial
↓
Shared Validation
↓
Asset Processing（按需）
↓
PPT Build
↓
Font / OOXML Audit
↓
Microsoft PowerPoint COM Render
↓
Structural QA
↓
Visual Reviewer
↓
Pass / Revise / Critical / Technical Failure
↓
必要时 Targeted Patch
↓
仅重跑受影响阶段
↓
Reviewer Recheck
↓
Deterministic Delivery Gate
↓
Delivered / Delivered with Warnings / Failed
```

核心目标不是减少必要阶段，而是：

> 避免一个局部或技术错误导致整个链路从头再来。

---

# 7. Layout Planner Initial

## 7.1 调用条件

必须满足：

```text
Runtime Ready
+
Input Ready
```

才调用 Layout Planner。

## 7.2 输入

Layout Planner 至少接收：

- Design / Source Image；
- Approved / Source Slide Content；
- 页面资产；
- 页面规格；
- 用户视觉约束；
- 可编辑性规则；
- 重建规则。

## 7.3 输出

Layout Planner 输出：

```text
Reconstruction Specification
```

应描述：

- element id；
- element type；
- bbox；
- z-order；
- text；
- font；
- fill；
- stroke；
- connector relation；
- asset reference；
- editable / raster strategy；
- 必要的对象属性。

Layout Planner 不直接构建 PPT。

---

# 8. Shared Validation

## 8.1 目的

Layout Planner 输出在进入正式 Build 前必须经过统一验证。

必须避免：

```text
Planner认为合法
↓
Finalizer / Builder又使用另一套规则判非法
```

因此：

> Planner Candidate Validation 与后续 Final Validation 应尽可能共享同一套 Schema、路径、语义和跨元素验证器。

## 8.2 验证层

至少包括：

### Schema Validation

检查：

- 必填字段；
- 类型；
- 枚举；
- 数据结构。

### Semantic Validation

检查：

- bbox 合法；
- z-order 合法；
- 页面边界；
- connector 关系；
- 文本安全区域；
- 资产引用；
- 可编辑性策略。

### Cross-element Validation

检查：

- connector 起点 / 终点；
- 元素重叠关系；
- 必需元素；
- 主要结构一致性；
- 元素 ID 唯一性。

### Path Validation

检查：

- 资产路径是否在允许范围；
- 禁止危险相对路径；
- 禁止越过任务工作目录访问未授权文件。

---

# 9. Validation Failure 分类

验证失败必须区分性质。

## 9.1 Mechanical / Deterministic Correction

可以由 Runtime 自动修正的机械性问题，例如：

- 路径分隔符标准化；
- 可安全归一化的数值格式；
- 明确无语义影响的默认字段；
- 临时文件路径标准化；
- 纯格式问题。

处理：

```text
Normalize
↓
Revalidate
```

不调用 Layout Planner。

## 9.2 Local Specification Error

例如：

- connector endpoint 进入文本安全区；
- 单个 bbox 越界；
- z-order 错误；
- crop 参数问题；
- 单个对象类型不合适；
- 资产路径需要在允许路径范围内修正。

处理：

```text
Structured Validation Issues
↓
Layout Planner Targeted Patch
↓
Revalidate
```

只允许修改受影响字段 / 元素。

## 9.3 Global Understanding Error

例如：

- 漏掉主要内容区；
- 页面结构整体理解错误；
- 关键视觉关系完全错误；
- 将主要视觉模块整体识别错；
- 大量元素分类错误。

此时才允许：

```text
Full Semantic Replan
```

User Mode 中 Full Semantic Replan 必须有明确上限。

默认策略：

> Initial Planning 之后，最多允许 1 次 Full Semantic Replan。

Targeted Patch 不计入 Full Semantic Replan 次数。

---

# 10. Asset Processing

## 10.1 按需执行

资产处理必须根据 Reconstruction Spec 判断是否需要。

如果页面：

```text
0 raster assets
0 svg assets
```

应走：

```text
Zero-Asset Fast Path
```

不得为了形式完整执行无意义的裁切、SVG 清洗或资产复制流程。

## 10.2 常见资产阶段

可能包括：

- crop；
- resize；
- alpha / transparency；
- SVG sanitize；
- local image normalization；
- image dimension verification。

## 10.3 资产阶段缓存

若：

- 原资产未变化；
- crop 参数未变化；
- 资产处理输出已通过；

则后续 Patch 不涉及该资产时应复用既有资产处理结果。

---

# 11. PPT Build

## 11.1 输入

Builder 接收：

- 已验证 Reconstruction Spec；
- Approved / Source Slide Content；
- 已准备资产；
- 页面尺寸。

## 11.2 Builder 负责

- 创建 PowerPoint 原生文本；
- 创建基础形状；
- 创建线条与连接线；
- 插入允许图片化的复杂资产；
- 设置 z-order；
- 保存 PPTX。

## 11.3 Builder 禁止

禁止：

- 修改权威文字；
- 自行重新规划页面；
- 因构建困难使用整页截图替代；
- 因技术问题请求重新生成大纲。

---

# 12. Font / OOXML Audit

Build 后应进行必要的确定性审计，例如：

- 字体引用；
- OOXML 结构；
- 必需对象存在性；
- PowerPoint 原生文本存在性；
- 异常整页图片检查；
- 其他结构风险。

审计器应避免已知的误报模式。

若审计器自身发生异常：

```text
technical_failure
```

而不是：

```text
semantic_planner_failure
```

---

# 13. Microsoft PowerPoint COM Render

## 13.1 目的

最终视觉审核必须基于实际 PPT 渲染结果，而不是仅根据 Builder 结构推测。

## 13.2 正式渲染环境

v2.0 第一阶段只允许：

```text
Windows
+ Microsoft PowerPoint Desktop
+ PowerPoint COM
```

实际渲染、打开验证和后续视觉审核输入必须来自 Microsoft PowerPoint COM 路径。

## 13.3 非当前范围

macOS、Linux、LibreOffice 和其他 Render Backend 不进入当前 Runtime 路径。如 PowerPoint COM 无法渲染，应进入受控 Technical Retry；超过上限后返回技术失败，不得切换到兼容 Backend。

---

# 14. Structural QA

## 14.1 目的

在进入 Visual Reviewer 前确认：

> 当前 PPT 在结构、内容和基本编辑性层面已经达到可审核状态。

## 14.2 至少检查

- PPTX 能正常打开；
- Microsoft PowerPoint COM 能正常渲染；
- 必需文字存在；
- 文字与权威内容一致；
- 主要对象存在；
- 对象未严重越界；
- 不存在明显字体异常；
- 资产有效；
- 主要文字为 native text；
- 不存在整页栅格化规避；
- 页面不是空白页；
- 关键关系结构存在。

## 14.3 Structural QA 失败分类

### Technical

例如：

- QA 工具异常；
- Render 临时失败；
- 文件访问异常。

进入：

```text
technical_retry
```

### Local Specification

例如：

- 单个元素越界；
- connector 错误；
- 某个 font size 不合格。

进入：

```text
Targeted Patch
```

### Global Semantic

仅当页面重建理解整体错误时：

```text
Full Replan
```

### Unrecoverable

无法恢复：

```text
failed
```

---

# 15. Technical Retry

## 15.1 定义

Technical Retry 用于：

> Spec 与内容语义没有变化，但某个确定性工具 / Backend 执行失败。

典型：

- Builder 异常；
- Renderer 异常；
- Font Audit 工具异常；
- QA 工具异常；
- 临时文件锁；
- 可恢复的 Office automation 异常。

## 15.2 原则

Technical Retry：

- 复用当前 Reconstruction Spec；
- 不调用 Layout Planner；
- 不计入 Full Semantic Replan；
- 不计入 2 次视觉定向修订；
- 从失败阶段继续；
- 必须有明确次数上限。

## 15.3 重试上限

v1.1 要求：

> 每种同阶段技术错误必须有限重试，不允许无限循环。

具体默认次数可由 Runtime 配置确定。

建议默认值：

```text
max_technical_retries_per_stage = 2
```

若连续达到上限仍失败：

```text
technical_failure
→ failed
```

或进入 Host 可明确处理的环境 / Backend 故障状态。

---

# 16. Visual Reviewer

## 16.1 调用前提

只有 Structural QA 通过后，才进入 Visual Reviewer。

## 16.2 Reviewer 必须尝试调用

正式用户流程：

> 每个最终页面必须尝试独立 Visual Reviewer。

不得为了节省时间直接跳过。

## 16.3 Reviewer 最小独立上下文

建议输入：

- Original Design / Source Image；
- PowerPoint 实际 Render；
- Approved / Source Slide Content 摘要；
- Structural QA 摘要；
- 页面元素简表；
- 审核规则。

Reviewer 不应看到：

- Layout Planner 完整对话；
- Layout Planner 私有推理；
- Host 的“应该通过”判断；
- 与当前审核无关的完整日志；
- 不必要的历史上下文。

## 16.4 Reviewer 至少检查

- connector topology；
- connector endpoints；
- key proportions；
- crop boundaries；
- background seams；
- visual depth；
- typography hierarchy；
- 页面整体布局；
- 关键元素位置；
- 风格一致性；
- 内容遗漏；
- 编辑性规避。

## 16.5 Reviewer 输出

至少支持：

```text
pass
revise
critical
technical_failure
```

Issue 应具有结构化定位：

```text
issue_id
check
severity
target_element_ids
observation
requested_change
evidence_region
```

---

# 17. Reviewer 技术失败

如果 Reviewer：

- timeout；
- service unavailable；
- tool unavailable；
- 其他技术原因未能正常返回；

且：

```text
Structural QA = pass
Content Accuracy = pass
Editability = pass
```

则：

> 不得因此重新调用 Layout Planner。

进入：

```text
delivered_with_warnings
```

并明确：

```text
visual review incomplete
```

注意：

> 只有 Reviewer“没有完成审核”才可以走该降级路径。

如果 Reviewer 已正常返回并确认存在 Major / Critical 问题，则不能伪装成“Reviewer 不可用”进行降级交付。

---

# 18. Targeted Patch

## 18.1 目的

Targeted Patch 用于：

> 修复已明确定位的局部 Spec / Visual 问题。

## 18.2 输入

至少包含：

- 当前 Reconstruction Spec；
- 当前 Render；
- Design / Source Image；
- Structural QA Summary；
- Normalized Reviewer Issues；
- 受影响元素摘要；
- 允许修改的字段 / 路径。

## 18.3 Patch 原则

Patch 必须：

- 只针对明确 issue；
- 优先只修改受影响元素；
- 不改 Approved / Source Slide Content；
- 不默认重新规划整页；
- 不改变无关资产；
- 不无理由重新执行未受影响阶段。

---

# 19. Patch 后重跑阶段规则

Patch 后不能默认：

```text
从 Layout Planner Initial 全部重新跑
```

应根据变化类型决定起点。

| Patch 类型 | 最早重跑阶段 |
|---|---|
| text box / shape / line 坐标 | Build |
| font size / fill / stroke / z-order | Build |
| connector endpoint | Build |
| 同一资产的图片位置 | Build |
| crop 参数变化 | Asset Crop |
| SVG 内容变化 | SVG Sanitize |
| 新增 / 删除图片资产 | Asset Processing |
| 仅 QA 规则修复 | QA |
| Reviewer 技术超时 | Reviewer |
| Render Backend 临时失败 | Render |

原则：

> 只重跑因输入变化而失效的阶段。

---

# 20. Visual Revision 计数

## 20.1 用户模式最大次数

用户模式：

> 最多 2 次定向视觉修订。

逻辑：

```text
Initial
↓
Reviewer
↓
Revision 1
↓
Reviewer
↓
Revision 2
↓
Reviewer
↓
Final Gate
```

## 20.2 不计入视觉修订的情况

以下不消耗 2 次视觉修订额度：

- Runtime Repair；
- Technical Retry；
- 机械性 Normalize；
- Reviewer 技术重试；
- QA 工具自身修复；
- Backend 临时恢复。

## 20.3 两次后仍有 Major / Critical

如果第二次定向修订后：

```text
Reviewer = major / critical
```

且问题仍阻塞交付：

```text
failed
```

不自动进行第三次、第四次视觉修订。

---

# 21. Resume 与 Stage Reuse

## 21.1 必须支持阶段恢复

Runtime 应支持：

```text
失败在哪里
→ 修复哪里
→ 从合理阶段继续
```

而不是：

```text
任何失败
→ 从 Layout Planner Initial 全部重跑
```

## 21.2 示例

若：

```text
Planner = pass
Assets = pass
Build = pass
Render = fail
```

修复 Renderer 后：

```text
Resume from Render
```

不重新执行 Planner、Assets、Build。

## 21.3 输入失效传播

每个阶段应根据其输入判断缓存是否仍有效。

原则：

```text
上游输入未变化
+
当前输出已通过
→ reuse
```

上游变化只使依赖该输入的下游阶段失效。

---

# 22. 缓存与哈希原则

第一版可采用：

- 输入文件 hash；
- Reconstruction Spec hash；
- Asset processing hash；
- Build input hash；
- Render input hash；

判断某阶段是否需要重新执行。

具体缓存 Schema 后续定义。

缓存必须服务于：

> 减少无意义重复工作。

不得因为缓存复杂度影响内容正确性。

---

# 23. run_state 原则

## 23.1 单一任务状态权威

单页 Runtime 应维护一个任务级权威状态，例如：

```text
run_state
```

不要同时建立多个互相竞争的：

```text
run_state
conversion_state
workflow_state
```

作为同一单页任务的权威控制来源。

## 23.2 建议记录

至少包括：

- task id；
- slide id；
- workflow mode；
- current stage；
- runtime backend；
- planner call count；
- full semantic replan count；
- targeted revision count；
- technical retry count；
- reviewer status；
- QA status；
- delivery status；
- stage artifacts；
- stage hashes；
- last failure classification。

具体字段在 Artifact / State 契约中定义。

---

# 24. 错误分类

所有失败应至少归入以下类别：

## 24.1 environment_failure

Runtime 无法达到当前任务所需能力。

## 24.2 technical_failure

工具、Renderer、Builder、Audit、QA 等确定性组件执行失败。

## 24.3 specification_failure

Reconstruction Spec 局部或整体不合法。

## 24.4 content_failure

权威内容缺失、冲突或无法可靠确定。

## 24.5 visual_review_failure

Reviewer 正常返回并发现阻塞性交付的视觉问题。

## 24.6 unrecoverable_failure

无法通过 Runtime Repair、Technical Retry、Targeted Patch 或有限 Replan 修复。

禁止使用：

```text
unknown error
→ retry everything
```

作为默认恢复策略。

---

# 25. User Mode

User Mode 面向实际用户任务。

目标：

> 保留必要质量 Gate，同时减少无意义日志、评分和重复执行。

User Mode 特征：

- Fast Preflight；
- Layout Planner；
- Shared Validation；
- Zero-Asset Fast Path；
- Stage Reuse；
- Technical Retry；
- Targeted Patch；
- Visual Reviewer 必须尝试；
- 最多 2 次视觉定向修订；
- Reviewer 技术故障允许满足条件的 Warning Delivery；
- 不设置固定总运行时长上限。

---

# 26. Development Mode

Development Mode 面向 Skill 开发、回归和质量验证。

可以额外保留：

- 完整 Agent 调用记录；
- 完整输入 / 输出 Manifest；
- 完整 Reviewer 原始结果；
- 详细 Stage Timing；
- 完整 QA Evidence；
- 更严格验证；
- 实验性诊断数据；
- 额外可视化对比结果。

Development Mode 不应改变核心质量定义。

它主要增加：

> 可观测性和诊断深度。

---

# 27. Delivery Gate

最终交付状态不由 Reviewer 单独决定。

由 Host 根据确定性 Gate 产生。

## 27.1 Delivered

满足：

```text
Structural QA = pass
Reviewer = pass
Content Accuracy = pass
Editability = pass
```

结果：

```text
delivered
```

## 27.2 Delivered with Warnings

满足：

- Structural QA = pass；
- Content Accuracy = pass；
- Editability = pass；
- Reviewer 已尝试调用；
- Reviewer 因技术原因未完成；
- 没有已知 Major / Critical issue。

结果：

```text
delivered_with_warnings
```

同时标记：

```text
visual review incomplete
```

## 27.3 Revision Required

Reviewer 正常返回：

```text
revise
```

且仍有修订额度：

```text
revision_required
```

随后进入 Targeted Patch。

## 27.4 Failed

包括：

- environment failure 无法恢复；
- technical failure 达到重试上限；
- content failure 无法解决；
- 第二次定向修订后仍有阻塞 Major / Critical；
- 整页栅格化规避；
- PowerPoint 无法正常构建 / 渲染；
- 不可恢复 Spec 问题。

结果：

```text
failed
```

---

# 28. 单页标准状态机

```text
INPUT_READY
↓
PRELIGHT
├─ fail → REPAIR → PRELIGHT
│                 └─ fail → FAILED
↓
PLANNING
↓
VALIDATING
├─ mechanical → NORMALIZE → VALIDATING
├─ local spec → PATCH → VALIDATING
├─ global semantic → FULL_REPLAN → VALIDATING
└─ unrecoverable → FAILED
↓
ASSET_PROCESSING
↓
BUILDING
↓
AUDITING
↓
RENDERING
↓
STRUCTURAL_QA
├─ technical → TECHNICAL_RETRY
├─ local spec → PATCH
├─ global semantic → FULL_REPLAN
└─ unrecoverable → FAILED
↓
REVIEWING
├─ pass → DELIVERY_GATE
├─ revise → PATCH
├─ critical → PATCH / FAILED
└─ technical_failure → WARNING_GATE
↓
DELIVERY_GATE
├─ delivered
├─ delivered_with_warnings
└─ failed
```

---

# 29. 多页任务中的单页隔离

虽然本规范针对单页 Runtime，但单页任务必须天然支持 Deck 场景中的隔离。

每页应拥有独立：

- task / slide id；
- run_state；
- Reconstruction Spec；
- Assets；
- Build output；
- Render；
- QA；
- Reviewer Issues；
- Patch；
- Delivery status。

一页失败不得自动：

- 删除其他页面；
- 污染其他页面状态；
- 触发所有页面重跑。

---

# 30. 可观测性

每个单页任务至少应记录：

## Agent

- Layout Planner 初始调用次数；
- Full Semantic Replan 次数；
- Targeted Patch 次数；
- Visual Reviewer 调用次数。

## Deterministic Stages

- Preflight；
- Asset Processing；
- Build；
- Audit；
- Render；
- Structural QA。

## Recovery

- Runtime Repair 次数；
- Technical Retry 次数；
- Failure Classification；
- Resume 起点。

## Timing

至少记录主要阶段耗时。

目的是：

> 能够判断真正的性能瓶颈发生在哪里。

---

# 31. 禁止行为

Single-Slide Runtime 明确禁止：

1. Runtime 未 Ready 就调用 Layout Planner；
2. 技术错误自动触发新的语义规划；
3. Reviewer timeout 导致重新 Layout Planner；
4. 单个 connector 错误导致整页重规划；
5. 任何失败默认从头开始；
6. 无限 Reviewer / Planner 循环；
7. OCR 覆盖 Approved Slide Content；
8. 用整页设计图冒充可编辑 PPT；
9. 已通过阶段在输入未变化时无理由重复执行；
10. Reviewer 直接决定最终 delivery；
11. Runtime Repair 消耗视觉修订额度；
12. 将环境故障伪装成内容失败。

---

# 32. 第一版验收场景

至少验证以下场景。

## S01 正常零资产页面

```text
Design Image
→ Planner
→ Zero-Asset Fast Path
→ Build
→ Render
→ QA
→ Reviewer
→ Delivered
```

验证：

- 不执行无意义资产处理；
- 主要文字可编辑；
- Reviewer 正常调用。

## S02 Environment Preflight Failure

模拟：

- Python 依赖缺失；
- Node 项目依赖缺失。

期望：

```text
Preflight Fail
→ Repair
→ Reverify
→ Continue
```

Layout Planner 调用次数不增加。

## S03 Technical Render Failure

模拟 Renderer 临时失败。

期望：

```text
Render Fail
→ Technical Retry
→ Render
```

不得重新 Planner。

## S04 Local Connector Error

模拟：

```text
connector endpoint incorrect
```

期望：

```text
Validation / Reviewer Issue
→ Targeted Patch
→ Build
→ Render
→ QA
→ Reviewer
```

不得 Full Replan。

## S05 Global Understanding Error

模拟页面整体结构明显误解。

允许：

```text
Full Semantic Replan
```

但必须受上限控制。

## S06 Reviewer Timeout

结构 QA 通过，但 Reviewer 技术超时。

期望：

```text
Reviewer attempted
→ no technical result
→ delivered_with_warnings
```

不得重新 Layout Planner。

## S07 两轮视觉修订仍失败

期望：

```text
Revision 1
→ Revision 2
→ still major
→ failed
```

不进行无限第三轮。

## S08 Resume

Build 已成功、Render 失败。

恢复后：

```text
Resume from Render
```

不得重新执行 Planner / Assets / Build。

## S09 Approved Content Protection

人为制造设计图文字与 Approved Slide Content 不一致。

最终 PPT 必须：

> 使用 Approved Slide Content。

## S10 Rasterization Evasion

尝试将整页设计图作为全页背景交付。

期望：

```text
Structural QA = fail
```

---

# 33. v1.1 核心冻结规则

第一版正式冻结：

```text
Runtime Ready
→ 才调用 Layout Planner
```

```text
Design Image
= 视觉基准
```

```text
Approved / Source Slide Content
= 文字基准
```

```text
Technical Failure
≠
Semantic Replan
```

```text
Local Issue
→ Targeted Patch
```

```text
Global Understanding Error
→ Limited Full Replan
```

```text
Reviewer
= 必须尝试独立调用
```

```text
Reviewer Technical Failure
+ Structural QA Pass
→ delivered_with_warnings
```

```text
Visual Targeted Revisions
≤ 2
```

```text
Input unchanged + stage passed
→ reuse
```

```text
No infinite retry
```

---

# 34. 最终规范定义

`Content to Editable PPT Skill` 的 Single-Slide Runtime v1.1 可以概括为：

> 在 Windows、Microsoft PowerPoint Desktop 和 PowerPoint COM 已通过 Fast Preflight 的前提下，以页面设计图作为视觉基准、以 Approved / Source Slide Content 作为文字权威源，由 Layout Planner 生成可编辑 PowerPoint 重建规格，再通过确定性资产处理、Build、Audit、Microsoft PowerPoint COM Render 和 Structural QA 建立可审核页面，最后由独立 Visual Reviewer 进行视觉检查。技术故障不得触发语义重规划，局部问题优先 Targeted Patch，只有整体理解错误才允许有限 Full Replan；所有重试必须有边界，已通过且输入未变化的阶段应复用。Reviewer 技术不可用时，在内容、可编辑性和结构 QA 均通过的条件下允许带警告交付；该降级只针对审核技术故障，不放宽 Windows 和 PowerPoint COM 的必需条件。
