# Stage 2 Guidance：已确认内容与线稿 → 高质量 PPT 设计图片

> **Status**：Final Guidance / 已确认架构指导  
> **Document type**：Stage 2 Guidance（Stage 2 指导）  
> **Last updated**：2026-08-31  
> **Scope**：定义 Stage 2 的目标流程、职责边界、输入输出、Prompt 生成方式、真实图片验证方式，以及面向 Stage 3 的重建友好约束。  
> **Authority note**：本文件用于指导后续原型、Benchmark 与实现；在新的 Proposal ADR 被验证并正式 Accepted 之前，不覆盖当前 Accepted ADR、正式 `SKILL.md` 或现有 Runtime。  

---

# 1. Stage 2 的目标

Stage 2 的任务不是重新规划内容，也不是直接生成可编辑 PowerPoint。

Stage 2 的目标是：

> **在 Stage 1 已确认的正式内容、页面结构与 Markdown Wireframe 基础上，由宿主代理（Host Agent）完成视觉设计细化，再由程序确定性编译生图 Prompt，调用图片生成模型生成真实 PPT 设计图，并通过代表页与整套页面验证视觉效果。**

最终链路：

```text
Stage 1 Approved Content
+
Stage 1 Markdown Wireframe
+
Stage 1 Machine-readable Semantic Structure
+
Stage 1 Structured Data
        ↓
Candidate Deck Visual System
        ↓
宿主代理进行视觉设计细化
        ↓
Slide Visual Design Spec
        ↓
Deterministic Prompt Compiler
        ↓
Final Image Prompt
        ↓
图片生成模型
        ↓
最终设计图
        ↓
User Visual Approval
        ↓
Approved Design Preview
        ↓
Stage 3
```

Stage 2 解决的是：

> **“已经确定要讲什么、怎么组织以后，这套 PPT 具体应该被设计成什么样，并稳定生成出来。”**

---

# 2. Authority 边界

正式 Authority 顺序保持：

```text
Accepted ADR / DECISIONS
↓
正式 SKILL.md / Runtime Contract
↓
当前 Runtime 实现与行为
↓
README 等用户说明
↓
Target Design / Research / Guidance
↓
External Evidence
```

本文件属于 Guidance，不得静默绕过已经 Accepted 的 ADR。

在 Visual-first 新路线完成 Benchmark、Proposal ADR 并被正式 Accepted 以前：

- 当前多页直接构建路线仍称 **Current Direct-Build Route**；
- 不提前正式命名为 Fast Mode；
- `run_pipeline.py` 继续作为 **Single-Slide Compatibility**；
- 现有单页 Planner / Reviewer / Recovery / Patch / Review Gate 能力继续保留。

---

# 3. Stage 2 输入

Stage 2 必须消费 Stage 1 已正式确认的成果。这些成果均由 Stage 1 宿主代理产生并经用户第一次确认。Stage 2 不关心 Stage 1 内部是否经历了大纲或线稿任务，也不消费所谓 Outline Planner 或 Wireframe Planner 的独立产物。

## 3.1 整套 PPT 级输入

至少包括：

```text
Presentation Brief
Storyline
Structured Outline
Stage 1 approval state
```

用于理解：

- 主题；
- 受众；
- 演示目标；
- 页面顺序；
- 跨页叙事关系。

---

## 3.2 单页正式内容

建议至少包括：

```yaml
slide_id: S06
order: 6
section: 研究设计
role: process

title: 三周干预围绕知识连接逐步展开

content_blocks:
  - id: phase_1
    label: 知识激活
    text: 第一周通过活动激活已有程序结构知识

  - id: phase_2
    label: 语法对应
    text: 第二周建立积木块与 Python 语法之间的对应关系

  - id: phase_3
    label: 独立迁移
    text: 第三周完成文本编程迁移

key_message: >
  三阶段形成递进关系，并最终完成独立迁移。

source_refs:
  - manuscript:Methods.3.2
```

其中：

- `title`
- `label`
- `text`
- 数字
- 专名
- 阶段名称
- 缩写
- 正式结论

都属于 **Stage 1 Text Authority**。

---

## 3.3 Markdown Wireframe

Stage 1 Markdown Wireframe 是：

> **单页 Structural / Topology Authority（结构与拓扑权威）**

它冻结页面主要区域、内容归属、阅读方向、逻辑关系和结构拓扑，但不冻结最终视觉几何、比例、留白或视觉重心。

目标级别是 **L2 结构线稿**。

它至少要说明：

1. 页面有哪些主要区域；
2. 正式内容分别属于哪个区域；
3. 内容之间的空间关系；
4. 内容之间的逻辑关系；
5. 阅读方向；
6. 主视觉位置或作用；
7. 哪些信息需要强调。

例如：

```text
┌──────────────────────────────────────┐
│ 标题                                 │
│                                      │
│ [第一周] → [第二周 ★] → [第三周]     │
│                           ↓          │
│                       [最终结果]      │
└──────────────────────────────────────┘

关系：三阶段递进
阅读方向：左 → 右
重点：第二阶段
最终落点：独立迁移
```

Stage 2 不重新选择或改变 Stage 1 已确认的页面结构与语义拓扑；但可在该结构约束内决定最终视觉构图实现。

---

# 4. Stage 2 输出

Stage 2 正式输出不是单一 PNG，而是一组有 Authority 区分的交付物：

```text
Validated Deck Visual System
+
Slide Visual Design Specs
+
Final Image Prompts
+
Generated Slide Images
+
Visual Review Results
+
Approved Design Preview
+
Stage 3 Handoff Metadata
```

其中：

- **Stage 1**：文字、数据、逻辑 Authority；
- **Approved Design Preview**：最终视觉 Authority；
- **Slide Visual Design Spec**：Stage 3 的辅助结构证据；
- **Final Image Prompt**：派生执行产物，不是新的 Authority。

---

# 5. ① Stage 2 的范围

第 ① 项正式确定：

> **Stage 2 不止生成 Prompt，而是一直执行到真实图片生成与实际视觉效果验证。**

原因是：

> Prompt 的质量不能只通过阅读 Prompt 文本来证明，必须看真实图片结果。

因此 Stage 2 包括：

```text
视觉设计
↓
Prompt 编译
↓
图片生成
↓
图片审核
↓
视觉系统验证
↓
整套设计图生成
↓
用户视觉确认
```

Stage 2 不包括：

```text
可编辑 PowerPoint 重建
```

这一部分属于 Stage 3。

---

# 6. ② 谁负责视觉设计

第 ② 项正式确定：

> **Stage 2 的视觉理解与视觉设计由宿主代理直接完成。**

不新增独立：

```text
Visual Designer Agent
```

宿主代理是当前实际运行 Skill 的 Codex / Claude Code 等主 Agent。

宿主代理在 Stage 2 负责：

- 理解 Stage 1 内容；
- 理解 Markdown Wireframe；
- 理解整套视觉方向；
- 决定单页主视觉表达；
- 决定视觉层级；
- 决定留白与节奏；
- 决定图形语言；
- 将整套视觉系统落实到当前页；
- 输出结构化 `Slide Visual Design Spec`。

宿主代理不负责：

- 重新规划 Storyline；
- 重新决定 Stage 1 已确认的页面结构与拓扑；
- 修改 Stage 1 正式内容；
- 自行新增正式页面文字；
- 自由书写最终 Prompt。

图片生成模型负责生成设计图片，但不是 Agent；Prompt Compiler、上下文整理、图片调用和缓存均属于确定性程序或工具边界。Stage 2 v1 不新增独立视觉设计代理，视觉审核由宿主代理组织，不能把图片模型称为设计 Agent。

---

# 7. ③ 整套视觉系统如何确定

第 ③ 项正式确定采用：

> **Reference-first + Proposal-if-needed + Image-confirmed**

流程：

```text
Stage 1 已确认成果
↓
检查视觉输入
```

## 7.1 有参考 PPT / 图片

```text
宿主代理提取参考视觉规律
↓
Candidate Deck Visual System
```

可提取：

- 色彩体系；
- 字体层级；
- 留白；
- 图形语言；
- 图片使用方式；
- 阴影 / 材质；
- 页面密度；
- 标题与主体比例；
- 跨页一致性规律。

但不得机械复制单页 Layout。

---

## 7.2 无参考图，但用户视觉要求明确

例如用户明确：

```text
明亮
学术
编辑式
大留白
不使用卡片堆叠
```

宿主代理将其结构化为：

```text
Candidate Deck Visual System
```

---

## 7.3 无参考，也无明确视觉方向

宿主代理提供：

> **2–3 个具体视觉方向**

并推荐其中一个。

用户选择以后形成：

```text
Candidate Deck Visual System
```

不允许自动采用：

```text
academic → 蓝色论文模板
business → 深色咨询模板
education → 彩色卡片模板
```

这类僵化映射。

---

## 7.4 候选视觉系统必须经过真实图片验证

固定生成 **3 张代表页**：

1. Cover / 封面；
2. Typical Body / 典型正文页；
3. Complex Representative / 复杂或高难代表页。

三张页面：

> **必须属于同一个 Candidate Deck Visual System，而不是三个不同风格方案。**

流程：

```text
Candidate Deck Visual System
↓
生成 3 张代表页
↓
宿主代理 + 用户检查真实图片
```

如果不满意：

### 整体风格问题

```text
修改 Candidate Deck Visual System
↓
重新生成 3 张代表页
```

### 单页设计问题

```text
保持 Candidate Deck Visual System
↓
只修改对应 Slide Visual Design Spec
↓
只重新生成该页
```

通过后：

```text
Candidate Deck Visual System
↓
Validated Deck Visual System
```

这一步是 **Representative Design Gate**，用于锁定整套视觉系统。

它不是 Stage 2 最后的正式视觉确认。

---

# 8. ④ Structural / Topology Authority

第 ④ 项正式确定：

> **Stage 1 Markdown Wireframe 是页面结构与拓扑权威。Stage 2 不重新选择页面语义拓扑，也不进行与 Stage 1 无关的 Layout Routing。**

Stage 1 决定页面主要区域、内容区域归属、阅读方向、流程 / 连接 / 语义拓扑，以及主要视觉对象在结构中的作用。Stage 2 可在该结构约束内决定最终视觉构图实现、对象实际比例、留白、视觉重心、视觉层级、图形语言、材质与装饰。用户确认后的最终设计图成为 Stage 3 的最终视觉 Authority。

因此不把下面链路作为 Stage 2 Core：

```text
Layout Bank
↓
assign_layouts()
↓
layout family routing
```

Stage 2 可以决定的是：

> **同一个已确认布局拓扑具体“长什么样”。**

例如 Stage 1 已经确定：

```text
A → B → C
重点：B
```

Stage 2 可以设计成：

```text
连续迁移路径
```

也可以：

```text
渐进式节点
```

可以改变：

- 节点造型；
- 路径风格；
- 颜色强调；
- 留白；
- 视觉运动；
- 图片语言；
- 材质与装饰。

不能改变：

```text
A → B → C
```

为：

```text
A
↓
C
↓
B
```

也不能擅自从横向递进改成无关三栏卡片。

---

# 9. ⑤ 正式文字 Authority

第 ⑤ 项正式确定：

> **Stage 2 不允许自行生成新的正式页面文字。**

需要出现在最终 PPT 上的：

- 标题；
- 短标签；
- 阶段名；
- 数字；
- 单位；
- 缩写；
- 专名；
- 图注；
- 结论；

都应在 Stage 1 生成并确认。

Stage 2 可以：

- 换行；
- 分段；
- 改排版；
- 改字号层级；
- 加粗；
- 改颜色；
- 从原句中拆分原始子串；
- 高亮 Stage 1 已存在关键词。

Stage 2 不可以：

- 自创新 Label；
- 改写；
- 概括；
- 自动缩写；
- 修改数字；
- 修改专名；
- 增加解释；
- 增加结论；
- 改变因果关系；
- 改变时间关系；
- 改变递进关系。

正式规则：

```text
Text Authority
= Stage 1

Semantic Authority
= Stage 1 Content + Stage 1 Wireframe
```

图片模型不得拥有新的正式文本 Authority。

---

# 10. ⑥ Prompt 生成架构

第 ⑥ 项正式确定：

> **宿主代理负责设计，程序负责确定性编译 Prompt。**

采用：

```text
Stage 1 Approved Content
+
Markdown Wireframe
+
Deck Visual System
        ↓
宿主代理
        ↓
Slide Visual Design Spec
        ↓
Deterministic Prompt Compiler
        ↓
Final Image Prompt
        ↓
Image Model
```

---

## 10.1 宿主代理的设计输出

宿主代理不直接自由写 Final Prompt，而是输出结构化的：

> **Slide Visual Design Spec（单页视觉设计规格）**

建议保持“小型结构字段 + 少量自由描述”，避免做成复杂 DSL。

候选结构：

```yaml
slide_id: S06

visual_objective: >
  让观众直观看到三个教学阶段逐步完成知识迁移。

composition_elaboration: >
  保持 Stage 1 已确认的横向三阶段结构。
  使用一条连续发展的视觉路径连接三个阶段，
  不使用三个独立等宽卡片。

visual_hierarchy:
  - 第一阶段视觉权重较低
  - 第二阶段为视觉中心
  - 第三阶段向右展开，并连接最终结果

main_visual: >
  连续路径与三个阶段节点构成主体视觉。

graphic_language: >
  使用克制的几何形式与细线连接，
  避免无意义图标和装饰性科技元素。

whitespace: >
  主体集中在中部，顶部与左右保留明显留白。

important_overlap:
  - title remains above main_visual

constraints:
  - 不改变 Stage 1 已确认的结构、区域归属与语义拓扑
  - 不新增任何页面文字
  - 不修改阶段顺序
```

具体 Schema 可以在实现阶段收敛，但职责边界不变。

---

## 10.2 Prompt Compiler 的职责

Prompt Compiler：

> **只编译，不设计，不推理，不改写。**

程序负责：

```text
校验 Slide Visual Design Spec
↓
读取 Stage 1 正式文字
↓
读取 Markdown Wireframe
↓
读取 Deck Visual System
↓
读取参考图片信息
↓
注入固定禁止项
↓
按固定结构生成 Final Prompt
↓
Prompt QA
```

最终 Prompt 建议固定包含：

```text
1. 任务身份
2. 画布规格
3. 页面目标
4. 本页在整套 PPT 中的作用
5. Stage 1 正式页面文字
6. Stage 1 Markdown Wireframe / Structural-Topology Authority
7. 本页 Slide Visual Design Spec
8. Deck Visual System
9. 必要 deck_context / local_context
10. Reference Image Rules
11. Cross-page Consistency Rules
12. Reconstruction-aware Constraints
13. Universal Prohibitions
14. Output Requirements
```

---

## 10.3 Final Prompt 是派生产物

正式确定：

> **Final Prompt 不是 Source of Truth，不允许在 Compiler 之后再交给宿主代理自由润色。**

如果图片有问题：

```text
视觉设计问题
→ 修改 Slide Visual Design Spec

整套风格问题
→ 修改 Deck Visual System

Prompt 编译遗漏
→ 修改 Prompt Compiler

图片模型执行问题
→ Retry / Provider / Model 层处理
```

禁止：

```text
生成图片失败
→ 手工直接改 Final Prompt
→ 留下不可追踪的 Prompt Patch
```

---

# 11. ⑦ 面向 Stage 3 的重建感知设计

第 ⑦ 项正式确定采用：

> **Reconstruction-aware Hybrid（重建感知的混合设计）**

核心原则：

> **Stage 2 仍然以高质量视觉设计为主，但在不明显降低设计效果的前提下，为 Stage 3 保留必要的可编辑重建条件。**

不是：

```text
Stage 2 完全不管 Stage 3
```

也不是：

```text
为了可编辑，
Stage 2 只能使用简单 Shape + Text
```

---

## 11.1 Rule 1 — 正式文字分离

> **Stage 1 已确认的正式文字、数字和 Label，不应成为复杂生成视觉不可分割的一部分。**

避免：

```text
3D 插画内部直接烤入
“32.6%”
“Knowledge Transfer”
“Phase 2”
```

因为 Stage 3 会被迫：

```text
OCR
→ 擦字
→ Inpaint
→ 再放 Native Text
```

正式文字应优先保持为可独立识别的内容区域。

---

## 11.2 Rule 2 — 复杂视觉边界清楚

> **照片、插画、3D、纹理、复杂装饰等可以自由设计，但优先形成边界清楚、可独立保留的视觉对象或区域。**

允许：

- 3D；
- Glow；
- 复杂渐变；
- Texture；
- 插画；
- 照片；
- 杂志式视觉；
- 高级构图；
- 局部重叠。

不要求这些元素全部转成 PowerPoint Shape。

目标是：

```text
复杂视觉
→ Stage 3 可作为独立 PNG / SVG / Image Asset

正式内容
→ Native Text / Shape / Chart
```

---

## 11.3 Rule 3 — 语义结构保留

对于：

```text
Chart
Table
Flow
Timeline
Connector
Relationship Diagram
```

其：

```text
数据
逻辑
顺序
关系
```

继续由 Stage 1 / Wireframe 保存。

Stage 2 负责：

> **视觉表现**

Stage 3 负责：

> **根据 Stage 1 结构 + Stage 2 Approved Design Preview 重建 Native Object。**

例如：

```text
Stage 1 Data
+
Stage 2 Chart Visual
↓
Stage 3
Native Chart Reconstruction
```

而不是：

```text
Stage 2 PNG
↓
OCR 数字
↓
猜 Chart
```

---

## 11.4 Rule 4 — 保留重建元数据

Stage 2 不只向 Stage 3 交：

```text
slide_06.png
```

还必须保留：

```text
Slide Visual Design Spec
```

Stage 3 输入应至少包括：

```text
Stage 1 Approved Content
+
Stage 1 Markdown Wireframe
+
Approved Design Preview
+
Slide Visual Design Spec
```

Authority 关系：

```text
Stage 1
→ 文字 / 数据 / 逻辑 Authority

Approved Design Preview
→ 视觉 Authority

Slide Visual Design Spec
→ 辅助结构证据
```

Visual Spec 不得覆盖用户已经确认的设计图片。

图片生成只产生页面的视觉表示，不终止、不替换 Stage 1 已确认的语义结构。Stage 1 中的正式内容、稳定对象编号、区域关系、连接关系以及 Chart / Table 结构化数据，应继续作为独立 Authority 直接传递给 Stage 3。

### Stage 2 新增重要视觉对象的稳定编号

Stage 2 新增且 Stage 3 需要独立处理的重要视觉对象，应分配稳定 `visual object ID`：包括需要独立裁切、定位 / 缩放、控制 z-order，或与正式文字、Chart、Table、Card 等重要重叠的对象（如大型人物插画、产品图、重要 3D Object 或大面积 Glow）。微小、低影响装饰不强制逐个编号。布局规划代理可有限补充低影响装饰，但不得借此重新发现或重解释整页语义结构。

```text
Stage 1 已确认内容 + 语义结构 + 结构化数据
        │
        ├──────────────────────────┐
        │                          │
        ↓                          │
Stage 2 视觉设计                   │
↓                                  │
图片生成模型                       │
↓                                  │
用户确认最终设计图                 │
        │                          │
        └─────────────┬────────────┘
                      ↓
                   Stage 3
```

> 最终设计图是 Stage 3 的视觉标准，但不是 Stage 3 唯一的信息来源。

---

## 11.5 Useful Editability

Stage 3 的目标正式采用：

> **Useful Editability（有用的可编辑性），而不是 Pixel Editability。**

建议目标边界：

| 元素 | Stage 3 目标 |
|---|---|
| 标题 / 正文 | Native Text |
| 数字 / Label | Native Text |
| Card / Panel / 基础几何 | Native Shape |
| Arrow / Connector | Native Shape / Connector |
| 简单流程图 | Native Shape + Connector |
| Formal Table | Native PowerPoint Table |
| Formal Chart | Native PowerPoint Chart |
| 标准 Icon | SVG / Shape |
| 照片 | Independent Image Asset |
| 复杂插画 | Independent Image Asset |

正式 Chart / Table 必须在 Stage 1 保留 authoritative structured data。Stage 2 不得批准最终设计明显无法由 Native PowerPoint Chart / Table 合理重建、但又要求 Stage 3 保持 Native editability 的方案；若数据缺失，必须返回 Stage 1 补齐，不允许 Stage 3 OCR、猜测或 Raster fallback。
| 3D / Texture | Raster / SVG Asset |
| 复杂装饰 | Local Raster / Asset |
| 整页设计图 | 不作为正常最终重建方案 |

禁止正常最终交付退化为：

```text
整页 PNG
+
少量可编辑文字
```

然后声称页面已经“可编辑”。

---

# 12. Stage 2 Core 最终流程

①～⑦ 确认后，Stage 2 Core 固定为：

```text
Stage 1 Approved Content + Markdown Wireframe
        ↓
检查视觉输入
        ↓
Candidate Deck Visual System
        ↓
宿主代理进行视觉设计细化
        ↓
Slide Visual Design Spec
        ↓
Deterministic Prompt Compiler
        ↓
Final Image Prompt
        ↓
Image Model
        ↓
Generated Slide Image
        ↓
宿主代理组织视觉审核
        ↓
Representative Design Gate
        ↓
Validated Deck Visual System
        ↓
剩余页面 Visual Specs
        ↓
批量 Prompt Compile + Image Generation
        ↓
Full-deck Visual Review
        ↓
第二次正式用户确认
        ↓
Approved Design Preview
        +
Slide Visual Design Specs
        +
Stage 1 Authority
        ↓
Stage 3
```

---

# 13. 代表页验证与整套页面生成

## 13.1 Representative Design Gate

固定：

```text
Cover
Typical Body
Complex Representative
```

共 **3 页**。

这三页用于验证：

- 风格是否正确；
- 跨页是否一致；
- 图片模型能否实现设计意图；
- 页面是否出现明显模板感；
- 是否存在 Card Spam；
- 是否存在伪文字；
- 是否保持 Stage 1 已确认的结构与拓扑；
- 是否具备基本 reconstruction friendliness。

---

## 13.2 代表页通过以后

才允许：

```text
Validated Deck Visual System
↓
Full-deck Generation
```

剩余页面：

- 可以按 4–6 页批量由宿主代理输出 Visual Specs；
- Prompt Compiler 批量确定性编译；
- 已通过页面尽量缓存；
- 单页失败只重新处理失败页；
- 不因一页失败重生整个 Deck。

---

# 14. Visual Review 的职责

Stage 2 Visual Review 检查真实图片，而不是只看 Prompt。

至少检查：

```text
视觉专业度
构图
信息层级
留白与节奏
内容表达是否正确
Page Role 是否匹配
卡片化 / 模板感
跨页一致性
伪文字 / 错字 / 数字错误
Stage 1 Wireframe 是否被破坏
Stage 3 Reconstruction Friendliness
```

文字错误需区分：

### Minor visual glyph issue

如果只是图片中文字轻微 Glyph 错误，而 Stage 1 Authority 完整：

> 可以记录为图片层问题，不自动修改 Stage 1。

### Serious semantic error

例如：

```text
数字改变
专名改变
新增随机 Label
结论改变
```

应判为 Serious Failure。

---

# 15. Retry、缓存与成本控制

Stage 2 必须是有界执行流程。

## 15.1 Retry

不得无限循环。

例如：

```text
max_generation_attempts = 3
```

具体值可在 Runtime 实现阶段确定，但必须存在明确上限。

---

## 15.2 Cache

如果：

```text
Cover   PASS
Body    PASS
Complex FAIL
```

只重新生成：

```text
Complex
```

不得默认把三页全部重跑。

整套 PPT 同理。

---

## 15.3 Fail-fast

视觉系统尚未通过 3 页代表页：

> 不允许直接生成整套 PPT。

避免把错误视觉方向扩散到 20 页以后再返工。

---

# 16. Stage 2 Benchmark Gate

在修改正式 Runtime / Accepted ADR 前，先用真实 Stage 1 输出验证 Stage 2。

## Round A — 验证 Prompt Pipeline

固定：

- 同一 Stage 1 内容；
- 同一 Markdown Wireframe；
- 同一图片模型；
- 同一尺寸；
- 同一参考图片；
- 能固定的 API 参数全部固定。

### Baseline

```text
Stage 1
↓
简单直接 Prompt
↓
同一图片模型
```

### Candidate

```text
Stage 1
↓
宿主代理 Visual Design Spec
↓
Deterministic Prompt Compiler
↓
同一图片模型
```

---

## A1 — 3 张代表页

```text
Cover
Body
Complex
```

A1 不通过：

> 停止，不跑整套。

---

## A2 — 8–10 页连续 PPT

检查：

- 跨页一致性；
- 页面多样性；
- 风格漂移；
- Cardization；
- Prompt Pipeline 是否稳定。

---

## A3 — 稳定性

选择 1–2 张关键页，各重新生成 3 次。

如果图片模型没有公开 Seed / Sampling：

> 不假装确定性，只记录实际稳定性。

---

## Round B — 图片模型比较

只有 Round A 证明 Prompt Pipeline 有价值以后，才比较图片模型。

例如：

```text
Model A / B / C
×
同样 3 页
```

再对 Top 1–2 跑 8–10 页。

避免同时改变：

```text
Prompt Pipeline
+
Image Model
```

导致无法判断效果来自哪里。

---

# 17. Benchmark 评分维度

建议总分 100：

| 维度 | 分值 |
|---|---:|
| 第一眼专业度 | 15 |
| 构图 | 15 |
| 信息层级 | 10 |
| 留白与节奏 | 10 |
| 内容表达正确性 | 10 |
| Page Role 匹配 | 10 |
| AI 模板感 / Card 化控制 | 10 |
| 跨页视觉系统一致性 | 10 |
| Stage 3 重建友好度 | 10 |

同时记录：

```text
Provider
Model
Page Count
Calls
Success / Failure
Regenerations
Latency
Cost
Reference Image Usage
```

Benchmark Result 只允许：

```text
Passed
Failed
Inconclusive
```

只有：

```text
Passed
```

才允许进入新的 Proposal ADR 与正式 Runtime 迁移。

---

# 18. 明确不采用的 Stage 2 设计

当前不采用：

```text
独立 Visual Designer Agent
```

不采用：

```text
Stage 2 Layout Router
```

不采用：

```text
每页由大模型自由写 Final Prompt
```

不采用：

```text
Prompt Compiler 后再让 LLM polish Prompt
```

不采用：

```text
Stage 2 自动重写正式内容以适应图片
```

不采用：

```text
为了 Stage 3 禁止所有复杂视觉
```

不采用：

```text
整页 Raster 作为正常“可编辑”交付策略
```

---

# 19. 当前外部项目的参考角色

Stage 2 不照搬任何一个项目，而是按职责吸收成熟做法。

## Prompt / 视觉设计侧

### Future Slide

主要借鉴：

> 宿主代理应该考虑哪些视觉设计问题。

包括：

- visual intent；
- hierarchy；
- main visual；
- anti-card；
- anti-generic；
- composition quality。

### `ningzimu/codex-ppt-skill`

主要借鉴：

> 宿主代理完成设计以后，由程序如何确定性打包 Prompt。

包括：

- self-contained page job；
- deck_context；
- local_context；
- fixed prompt sections；
- worker execution boundary。

### `JuneYaooo/gpt-image2-ppt-skills`

主要借鉴：

- deterministic Prompt Compiler；
- prepare-only；
- prompt artifact；
- metadata；
- batch execution。

不采用其 Layout Routing 作为当前 Stage 2 Core。

### Design Image Studio

主要借鉴：

> 设计信息与 Final Prompt 分层。

---

## Reconstruction-aware 侧

源码研究表明，多数成熟重建路线收敛到：

```text
Native Text
+
Native Semantic Structure
+
Bounded Complex Visual Assets
```

重点参考方向包括：

- `ningzimu/image-to-editable-ppt-skill`
- `Kevinyyy1/image-to-editable-pptx-v2`
- `Hasasasa/html-to-editable-pptx`
- `jacksonqian1/visual-to-editable-ppt`
- `w1163222589-coder/slide-image-to-editable-pptx`

共同证据支持：

> **复杂视觉无需强制 Native，但正式文字与重要语义结构应尽量与复杂视觉资产分离。**

---

# 20. Stage 2 当前冻结决策总表

| # | 架构问题 | 最终决策 |
|---|---|---|
| ① | Stage 2 到哪里结束 | 到真实图片生成、视觉审核与整套设计图正式确认 |
| ② | 谁负责视觉设计 | 宿主代理（Host Agent）；Stage 2 v1 不新增独立视觉设计代理 |
| ③ | 视觉风格怎么确定 | Reference-first；必要时 2–3 个方向；3 张代表页真实图片验证后锁定 |
| ④ | 页面结构与最终视觉分别由谁决定 | Stage 1 Markdown Wireframe 冻结结构与拓扑；Stage 2 在该约束内完成最终视觉构图，用户确认后的最终设计图成为 Stage 3 的视觉 Authority |
| ⑤ | Stage 2 能否改正式文字 | 不能；短 Label 等必须在 Stage 1 确认 |
| ⑥ | Final Prompt 怎么产生 | 宿主代理 → Slide Visual Design Spec → Deterministic Prompt Compiler |
| ⑦ | 如何照顾 Stage 3 | Reconstruction-aware Hybrid；视觉优先，同时分离正式内容、保留语义结构与重建元数据 |

---

# 21. 一句话版本

Stage 2 可以最终概括成：

> **Stage 1 决定“讲什么、怎么组织”；宿主代理决定“这一页具体怎么设计”；程序负责“守 Authority、确定性编译并执行 Prompt”；图片模型负责“真正画出来”；真实图片负责验证设计是否成立；Stage 2 同时保留少量重建友好约束，使 Stage 3 能在不牺牲视觉质量的情况下完成 Useful Editability。**
