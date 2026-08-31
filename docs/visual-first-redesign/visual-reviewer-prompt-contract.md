# 视觉审核代理 Prompt Contract

> **Status**：Working Guidance / Pre-ADR Prompt Contract  
> **Document type**：Stage 3 Agent Contract  
> **Applies to**：视觉审核代理（Visual Reviewer Agent）  
> **Design baseline before contract drafting**：`8122f32 docs: refine visual-first agent architecture`
> **First repository commit containing this contract**：`03d66aa docs: add stage 3 prompt contracts`
> **Last updated**：2026-08-31  
> **Runtime authority**：非运行权威；不覆盖当前正式 `visual_reviewer.md`、Agent YAML、Schema、Runtime 或 Accepted ADR。  
> **Decision dependency**：只有在 Stage 2 Benchmark 通过并进入后续 ADR / Implementation 后，才允许据此修改正式 Prompt 与 Runtime。

---

# 1. 文档目的

本文档不编写最终 `visual_reviewer.md` 提示词全文。

本文档先冻结 Visual-first Stage 3 中视觉审核代理的稳定任务合同，明确：

1. 视觉审核代理负责什么；
2. 它接收哪些输入；
3. 它从哪里获得审核上下文；
4. 它审核哪些视觉问题；
5. `PASS / PASS_WITH_MINOR_DIFFERENCES / REVISION_REQUIRED / BLOCK` 如何区分；
6. 当页面需要修订时，它必须如何定位问题；
7. 它可以给多具体的修改建议；
8. 它与布局规划代理、结构 QA、Final Deck QA 的职责边界；
9. 什么情况下需要再次触发视觉审核。

后续正式 Prompt、输出 Schema、Reviewer 调用包和 Runtime 适配必须遵守本合同。

---

# 2. 角色定位

视觉审核代理是 Stage 3 中负责**独立判断重建后的 PowerPoint 页面是否已经达到视觉交付标准**的专业代理。

它不是：

- 页面设计者；
- 布局规划者；
- 内容校对者；
- 数据验证器；
- PPT 构建器；
- 编辑性检查器。

它的核心任务是：

> **比较用户确认后的最终设计图与当前 PowerPoint 渲染结果，结合权威结构上下文和确定性 QA 证据，判断当前页面是否已经达到高视觉一致性和实用可编辑性的交付水平。**

---

# 3. 独立上下文原则

视觉审核代理必须与布局规划代理保持独立上下文。

不得直接继承：

- Layout Planner 的完整对话历史；
- Layout Planner 的自然语言推理；
- Host Agent 对页面的自由总结；
- 其他 Agent 对页面“为什么这样设计”的解释。

原因：

> Reviewer 必须独立判断最终结果，而不是重复 Planner 已经形成的解释。

推荐调用结构：

```text
Approved Design
+
Current Render
+
Deterministically Compiled Review Context
+
QA Evidence
        ↓
Fresh Visual Reviewer
```

---

# 4. Reviewer Context 不由 Agent 总结

视觉审核代理不读取完整 Stage 1 原始文档，也不依赖 Host Agent 临时总结。

它接收的是：

> **由确定性 Context Compiler 生成的审核上下文投影。**

该 Context Compiler：

- 不是 Agent；
- 不调用 LLM；
- 不重新解释页面；
- 不重新生成事实；
- 只按照固定规则从权威 Artifact 中机械抽取 Reviewer 所需字段。

其来源可以包括：

```text
Stage 1 Canonical Content
+
Stage 1 Semantic Structure
+
Stage 2 Important Visual Objects
+
Canonical Reconstruction Plan
+
Structural / Editability QA Evidence
        ↓
Deterministic Context Compiler
        ↓
Reviewer Context
```

Reviewer Context 不是新的 Source of Truth。

它只是已有权威数据的只读运行时投影。

---

# 5. Reviewer 输入合同

本合同冻结输入信息类别，不冻结具体文件名。

视觉审核代理至少需要以下输入。

## 5.1 用户确认后的最终设计图

作为页面最终视觉标准，用于判断：

- 构图；
- 主要对象位置；
- 大小比例；
- 留白；
- 视觉层级；
- 重叠关系；
- 字体视觉；
- 颜色；
- 阴影；
- 风格。

---

## 5.2 当前 PowerPoint 渲染图

这是 Reviewer 实际审核的页面结果。

Reviewer 不直接读取 PowerPoint XML 进行视觉判断。

---

## 5.3 审核上下文投影

至少应能表达：

```text
page identity
required objects
content refs
visual objects
relations
representation expectations
accepted reconstruction plan refs
```

概念示例：

```yaml
page_id: slide_03

required_objects:
  - id: title
    role: title
    content_ref: content.title

  - id: step_1
    role: process_step
    content_ref: content.step_1

  - id: step_2
    role: process_step
    content_ref: content.step_2

  - id: chart_01
    role: chart
    data_ref: data.chart_01

visual_objects:
  - id: hero_illustration
    role: complex_visual

relations:
  - type: flow
    from: step_1
    to: step_2

representation_expectations:
  - id: chart_01
    type: native_chart
```

具体字段名与最终 Schema 不在本合同冻结。

---

## 5.4 QA Evidence

视觉审核发生在确定性结构 / 可编辑性 QA 之后。

Reviewer 至少应知道：

```yaml
qa_summary:
  structural: PASS
  editability: PASS
```

Reviewer 不负责重新验证：

```text
Chart 是不是真的 PowerPoint Chart
Table 是不是真的 PowerPoint Table
文字是不是 native text
是否存在整页 raster
```

这些由确定性 QA 负责。

---

# 6. Reviewer 不负责什么

视觉审核代理不得：

- 修改正式文案；
- 修改数字、单位、专名或结论；
- 重新计算 Chart / Table 数据；
- 判断 Chart / Table 的底层 OOXML 是否正确；
- 判断 PPT 对象是否真实可编辑；
- 重新规划整页；
- 输出新的 Reconstruction Plan；
- 生成新的几何坐标；
- 生成新的 crop box；
- 自行修改 PPT；
- 自行重新生图；
- 因为轻微视觉差异要求无限返工；
- 仅凭自己的“审美偏好”推翻用户已确认的最终设计。

---

# 7. 审核目标

视觉审核的目标不是：

> 与最终设计图逐像素一致。

而是：

> **判断当前 PPT 页面是否已经保持最终设计图的主要视觉意图，并达到用户可直接使用、必要时继续自行微调的水平。**

核心原则：

> **允许数值误差，不允许明显构图错误。**

---

# 8. 固定视觉审核维度

v1 冻结以下 7 类审核维度。

## 8.1 对象完整性

检查：

- 必需对象是否在页面中出现；
- 重要视觉对象是否明显缺失；
- 是否有对象被错误隐藏、裁掉或漏构建。

Reviewer 可以判断：

```text
step_2 视觉上是否缺失
```

但不负责重新验证：

```text
step_2 的正式内容是否语义正确
```

---

## 8.2 整体构图

检查：

- 页面主要区域是否基本一致；
- 页面视觉重心是否合理；
- 主要模块是否位于正确区域；
- 版式是否出现明显偏移、坍塌或错位。

允许轻微位置偏差。

不允许：

- 左右布局整体反转；
- 主区域被挤压到错误位置；
- 页面整体视觉重心明显漂移。

---

## 8.3 大小比例

检查：

- 主视觉是否明显过大或过小；
- 卡片、图表、表格是否比例失衡；
- 页面主要对象的相对大小是否合理。

允许：

- 小幅宽高差异；
- 用户可以自行拖动调整的轻微尺寸差异。

不允许：

- 辅助元素变成主视觉；
- 主视觉缩小到失去设计作用；
- 图表尺寸严重挤压正文。

---

## 8.4 层级关系

检查：

- 前后关系是否合理；
- 主次层级是否正确；
- 背景、装饰、内容对象是否位于合理层级。

不允许：

- 背景装饰压住正式文字；
- 原本位于人物前方的卡片错误被人物完全遮住；
- 视觉主次关系被重建结果颠倒。

---

## 8.5 重叠与遮挡

检查：

- 是否存在错误遮挡；
- 是否存在裁切主体；
- 重要对象间是否发生明显不合理重叠；
- 正式文字是否被图片、图表或其他对象覆盖。

这是 `REVISION_REQUIRED` 的高优先级触发类别。

---

## 8.6 视觉风格

检查：

- 颜色是否明显漂移；
- 字体视觉是否明显不协调；
- 圆角、阴影、透明度等是否发生足以破坏页面风格的偏差；
- 页面是否仍然属于用户确认的视觉系统。

不要求：

- 阴影强度完全一致；
- 圆角半径像素级一致；
- 字体渲染完全一致；
- Native Chart 的效果逐像素匹配设计图。

---

## 8.7 最终可用性

最终判断：

> 用户是否可以直接使用这一页，而不是必须先修明显错误才能使用？

如果用户只是：

> 想让页面更精致。

不应自动返工。

如果用户必须：

> 先修正遮挡、错位、严重比例失衡等问题，页面才能正常使用。

则应进入修订。

---

# 9. Reviewer 不重新审核正式数据正确性

以下内容不属于视觉审核代理职责：

```text
数字是否正确
Chart 数据是否正确
Table 数据是否正确
专业术语是否正确
Stage 1 结论是否正确
Native Chart / Table 是否真实原生
```

其权威来源与验证路径分别属于：

```text
Stage 1 Authority
+
Deterministic Structural / Editability QA
```

Reviewer 只判断这些对象**视觉上是否被正确实现**。

---

# 10. 四级判定状态

v1 固定为：

```text
PASS
PASS_WITH_MINOR_DIFFERENCES
REVISION_REQUIRED
BLOCK
```

---

# 11. PASS

含义：

> 页面整体已经达到交付标准，没有值得继续自动修订的问题。

典型情况：

- 构图正确；
- 主次比例正确；
- 层级正确；
- 无明显遮挡；
- 页面视觉风格基本一致；
- 用户可以直接使用。

处理：

```text
PASS
→ Accepted Page
```

不得再次调用 Layout Planner 进行自动修订。

---

# 12. PASS_WITH_MINOR_DIFFERENCES

含义：

> 页面存在轻微视觉差异，但不影响正常使用，没有必要为了进一步精修再次消耗 Agent 修订成本。

典型情况：

- 标题位置略有偏差；
- 卡片间距略有不同；
- 图片稍大或稍小；
- 圆角略有不同；
- 阴影深浅略有不同；
- 字体渲染稍有差异；
- Native Chart 与设计图存在轻微视觉差异；
- 用户可以在 PowerPoint 中自行完成小幅微调。

处理：

```text
PASS_WITH_MINOR_DIFFERENCES
→ Accepted Page
```

Runtime 行为与 PASS 相同。

保留该状态主要用于：

- Benchmark；
- Evidence；
- 质量统计；
- 区分“完全正常”与“轻微偏差但可接受”。

---

# 13. REVISION_REQUIRED

含义：

> 当前页面存在明显影响构图、阅读、层级、遮挡、重要比例或整体专业度的问题，但 Stage 3 仍然可以通过局部或有界修订解决。

典型情况：

- 人物明显遮挡正式文字；
- 主视觉比例严重失衡；
- 图表位置明显错误；
- 卡片组出现明显错位；
- 连接关系视觉表达明显错误；
- 某个对象明显超出页面；
- 复杂图片主体被错误裁切；
- 页面局部视觉重心明显破坏。

处理：

```text
REVISION_REQUIRED
→ Host Agent
→ Layout Planner Targeted Revision
```

---

# 14. REVISION_REQUIRED 必须尽量绑定对象 ID

只要 Reviewer 输出：

```text
REVISION_REQUIRED
```

原则上必须定位到稳定对象 ID。

例如：

```yaml
status: REVISION_REQUIRED
scope: local

affected_objects:
  - hero_illustration
  - step_3

issue_type:
  - scale
  - overlap

description:
  人物插画明显过大，并遮挡第三张卡片的重要文字区域。
```

不允许只返回：

```text
“页面右侧不太协调。”
```

因为这无法驱动定向修订。

---

## 14.1 允许 page-level scope 的情况

只有真正无法合理归因到少量对象的整页构图问题，才允许：

```yaml
scope: page
```

例如：

- 大量对象同时偏移；
- 整页视觉重心明显错误；
- 整体版式与最终设计完全不一致。

即使是 page-level issue，也应尽可能列出最主要的受影响对象。

---

# 15. Reviewer 可以给修改方向，但不能给新布局计划

Reviewer 可以给：

```text
人物过大
→ 建议缩小

图表位置偏低
→ 建议上移

人物遮挡卡片
→ 建议降低重叠或向右移动

卡片组整体偏下
→ 建议上移
```

即：

> **方向性修复建议。**

Reviewer 不得给：

```yaml
x: 0.681
y: 0.172
width: 0.243
height: 0.592
```

也不得输出：

- 新的 bbox；
- 新 crop box；
- 新 z-order plan；
- 新 Reconstruction Plan；
- 新 page layout。

职责边界：

```text
Visual Reviewer
→ 发现问题 + 指明修复方向

Layout Planner
→ 决定具体怎么改
```

---

# 16. BLOCK

含义：

> 当前问题不是一次 Stage 3 局部视觉修订可以合理解决。

典型情况：

## 16.1 上游对象缺失

Stage 1 明确要求：

```text
step_1
step_2
step_3
```

最终设计中明显没有：

```text
step_2
```

如果无法确认是 Stage 2 设计遗漏还是 Stage 3 对齐失败：

```text
BLOCK
```

---

## 16.2 Authority Conflict

例如：

```text
Stage 1：A → B → C
最终设计：A → C → B
```

Reviewer 不自行决定哪一个正确：

```text
BLOCK
```

---

## 16.3 Structured Data Missing

如果 QA / Context 显示：

```text
Native Chart / Table 所需权威数据不完整
```

则：

```text
BLOCK
```

而不是要求 Planner 猜数据。

---

## 16.4 Unsafe Reconstruction

例如：

- 复杂视觉与正式文字无法安全分离；
- Native-required object 无法满足重建政策；
- 设计本身需要回到 Stage 2 调整。

处理：

```text
BLOCK
→ 返回 Stage 1 / Stage 2
```

---

# 17. Reviewer Output 最小语义要求

具体 JSON 字段名与最终 Schema 不在本合同冻结。

但输出至少必须表达：

```text
overall status
review scope
affected object ids
issue category
issue description
revision direction
block reason（如果存在）
```

概念示例：

```yaml
status: REVISION_REQUIRED
scope: local

issues:
  - affected_objects:
      - hero_illustration
      - step_3

    issue_type:
      - overlap
      - scale

    description:
      人物插画明显过大，遮挡第三张卡片的重要内容。

    revision_direction:
      缩小人物并降低与 step_3 的重叠程度。
```

---

# 18. Reviewer 与 Layout Planner 的边界

```text
Layout Planner
→ 决定页面怎么重建

Visual Reviewer
→ 判断重建结果是否达到交付标准
```

Reviewer 不能变成第二个 Layout Planner。

Layout Planner 也不能自行替代 Fresh Reviewer。

两者必须保持角色分离。

---

# 19. Reviewer 与 Structural / Editability QA 的边界

```text
Structural / Editability QA
→ 判断“对象做法对不对”

Visual Reviewer
→ 判断“结果看起来对不对”
```

例如：

```text
chart_01 是不是真的 PowerPoint Chart
→ QA

chart_01 大小、位置、视觉层级是否合理
→ Visual Reviewer
```

---

# 20. Reviewer 默认只负责单页

v1 的视觉审核代理默认是：

> **Page-level Visual Reviewer**

标准页面闭环：

```text
Page Build
↓
Structural / Editability QA
↓
Visual Reviewer
↓
Accepted Page
```

---

# 21. Final Deck 不默认再次调用 Visual Reviewer

所有页面都 Accepted 后：

```text
Accepted Page Plans
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

Final Deck 阶段：

> **不默认再对整套 Deck 调用一次 Visual Reviewer。**

原因：

- 每页此前已经独立通过视觉审核；
- 全 Deck 再审属于重复成本；
- 长 Deck 会显著增加模型调用；
- Final Deck 主要需要检测 Shared Builder 是否造成重建漂移。

---

# 22. Final Deck 何时重新触发 Visual Reviewer

只有出现风险信号时才定向视觉复核。

例如：

- Final Deck 某页与 Accepted Page Render 出现明显 drift；
- Shared Builder 后发生字体变化；
- 对象层级变化；
- 页面错位；
- 图片裁切变化；
- 确定性 Deck QA 给出风险警告；
- Release / Field Validation 明确要求全 Deck 视觉复核。

默认：

```text
No Drift
→ No Additional Visual Reviewer
```

异常：

```text
Drift / Risk
→ Targeted Visual Re-review
```

---

# 23. 审核宽严原则

视觉审核必须优先避免两个极端。

## 23.1 不允许过严

以下情况通常不应触发自动修订：

- 几像素的位置差异；
- 小幅间距差异；
- 阴影深浅不同；
- 圆角轻微不同；
- 原生 PowerPoint 图表存在合理渲染差异；
- 用户可以很容易自行微调的细节。

---

## 23.2 不允许过松

以下情况必须明确指出：

- 正式内容被遮挡；
- 重要对象明显缺失；
- 页面构图严重偏离；
- 主次比例明显错误；
- 图片主体严重裁切；
- 层级关系明显错误；
- 页面已经不能直接正常使用。

---

# 24. 最终判断原则

Reviewer 应采用以下核心标准：

> **如果用户必须先修这个问题，页面才能正常使用，则应自动修订。**
>
> **如果用户只是想让页面更精致，则应通过。**

---

# 25. v1 明确不冻结的事项

本合同暂不冻结：

- 最终 `visual_reviewer.md` Prompt 全文；
- Few-shot 示例；
- 最终模型选择；
- Context 文件名；
- Context JSON Schema；
- Reviewer 输出 JSON Schema；
- severity 是否使用枚举或数值；
- confidence 字段；
- 数值化视觉相似度阈值；
- 最大 Reviewer 调用次数；
- Final Build Drift 的最终计算方法；
- 最终图像 diff 算法；
- Release 阶段是否强制 Whole-Deck Reviewer。

这些进入后续 Benchmark / ADR / Implementation 再冻结。

---

# 26. 冻结决策摘要

| 项目 | v1 决策 |
|---|---|
| Reviewer 上下文 | Fresh / independent context |
| Planner 历史 | 不继承 |
| Stage 1 全文 | 不直接读取 |
| Reviewer Context | 确定性 Context Compiler 生成 |
| Context 性质 | 权威 Artifact 的只读投影，不是新事实源 |
| 输入 | Approved Design + Current Render + Review Context + QA Evidence |
| 审核维度 | 对象完整性、构图、比例、层级、重叠、风格、最终可用性 |
| 数据正确性 | 不由 Visual Reviewer 重新验证 |
| 编辑性 | 不由 Visual Reviewer 检查 |
| 几何标准 | 不追求像素级复刻 |
| 判定状态 | PASS / PASS_WITH_MINOR_DIFFERENCES / REVISION_REQUIRED / BLOCK |
| PASS | 接受 |
| MINOR | 接受，保留 Evidence |
| REVISION | 触发 Layout Planner 定向修订 |
| REVISION 问题定位 | 尽量绑定稳定对象 ID |
| Reviewer 修复建议 | 只给方向，不给新坐标 / 新 Plan |
| BLOCK | 返回 Stage 1 / Stage 2，不在 Stage 3 硬修 |
| 审核粒度 | 默认单页 |
| Final Deck | 不默认再次调用 Reviewer |
| Final Deck 异常 | Drift / Risk 才定向复核 |

---

# 27. 最终工作流

```text
Stage 1 Authority
+
Stage 2 Important Visual Objects
+
Canonical Reconstruction Plan
+
Structural / Editability QA
        ↓
Deterministic Context Compiler
        ↓
Review Context
        │
        ├──────── Approved Design
        │
        └──────── Current Render
                    ↓
             Fresh Visual Reviewer
                    │
          ┌─────────┼───────────────┐
          │         │               │
          ↓         ↓               ↓
        PASS      MINOR          REVISION
          │         │               │
          └────┬────┘               ↓
               ↓              Layout Planner
          Accepted Page        Targeted Revision
                                    ↓
                               Rebuild + QA
                                    ↓
                                Re-review

BLOCK
↓
Return Stage 1 / Stage 2
```

全部页面接受后：

```text
Accepted Page Plans
↓
Shared Builder
↓
Final Deck
↓
Deterministic Deck QA
↓
Final Build Drift Check
        │
        ├─ No Drift
        │    ↓
        │  Delivery
        │
        └─ Drift / Risk
             ↓
          Targeted Visual Re-review
```

---

# 28. 结论

Visual-first Stage 3 的视觉审核代理不应是一个“重新设计页面”的第二设计师。

它应是一个独立、边界明确的视觉质量判定器：

> **在 Fresh Context 下，只基于用户确认后的最终设计图、当前 PowerPoint 渲染图、确定性生成的审核上下文投影和 QA Evidence，判断页面是否达到可交付水平；轻微差异直接接受，明显局部问题精确定位后交给布局规划代理定向修订，上游冲突或无法合理修复的问题明确阻断。**
