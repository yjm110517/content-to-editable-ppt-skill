# 外部项目与源码证据库

> **Status**：Evidence / Research（证据与研究）
> **Document type**：External Project & Source Review（外部项目与源码审查）
> **Authority**：无产品或架构决策权
> **Current runtime relationship**：不直接引入任何外部 Runtime；默认思想借鉴或阅读后重新实现
> **Depends on**：[`02-stage1-design.md`](../02-stage1-design.md)、[`03-stage2-research-and-decision.md`](../03-stage2-research-and-decision.md)
> **Next decision gate**：实施前锁定具体 Commit SHA；直接代码复用前完成 License / NOTICE 审计
> **Last updated**：2026-08-28

---

## 1. 外部项目使用规则

本文由此前的 GitHub 项目调研和源码分析草稿合并而来；原下载目录草稿不作为仓库依赖，也不进入当前权威链。

外部项目采用三级：

#### `idea_only`

思想借鉴。

例如：

```text
PPTAgent 使用 source indexes 绑定原始材料
↓
本项目重新设计为 source_refs
```

#### `reimplemented`

阅读源码，理解问题和实现方式，在本项目重新实现。

这是默认推荐方式。

#### `adapted / vendored`

直接复用或改编代码。

只有在确有必要时允许，并必须检查：

- License；
- Copyright；
- NOTICE；
- 文件级许可证；
- 与本项目许可证兼容性。

同时记录：

```text
source_project
source_commit
source_file
local_file
reuse_type
license
copyright
notice_required
```

---

## 2. Commit 冻结状态

原研究明确指出：

> 当前源码精读基于各仓库当时的 `main` / `master`；正式实施前必须锁定具体 Commit SHA。

但现有整理源文件没有保存具体 SHA。

因此本文统一记录：

```text
Source Commit SHA: TBD before implementation
```

在 Commit 未冻结前，任何源码级结论都是研究证据，不是稳定依赖合同。

---

## Stage 1 参考项目

### 3. PPTAgent

```text
Repository: icip-cas/PPTAgent
License: MIT
Source Commit SHA: TBD before implementation
Reuse level: idea_only / reimplemented
```

#### 项目级观察

最有价值：

- 页面 Purpose；
- 内容来源绑定；
- 功能页与内容页区分。

#### 源码级观察

已阅读：

```text
pptagent/roles/planner.yaml
pptagent/pptgen.py
```

`planner.yaml` 关注：

```text
document_overview
↓
选择 section / subsection
↓
建立大纲
↓
Slide Purpose
↓
source indexes
↓
相关图片
```

#### 对本项目的启示

```text
Slide Purpose
→ role / key_message

source indexes
→ source_refs
```

#### 不采用

- 不照搬其完整多 Agent 后续生成链；
- 不直接复制 Outline Schema；
- 不让 Stage 1 变成复杂 Agent Runtime。

---

### 4. Presenton

```text
Repository: presenton/presenton
License: Apache-2.0
Source Commit SHA: TBD before implementation
Reuse level: idea_only / reimplemented
```

#### 已阅读

```text
servers/fastapi/models/presentation_outline_model.py
servers/fastapi/utils/llm_calls/generate_presentation_outlines.py
```

#### 关键观察

- Outline 内容语义与视觉设计指令分离；
- Structured Output 后仍需本地校验；
- 用户输入、页数、语言等有明确优先级。

#### 对本项目的启示

```text
正式内容 Authority
≠
Visual Need / Design Instructions
```

#### 不采用

- 不直接复制其 Model；
- 不直接复制其 LLM Call Runtime。

Apache-2.0 代码如果未来直接复用，需要额外检查 LICENSE / NOTICE 要求。

---

### 5. baoyu-design

```text
Repository: JimLiu/baoyu-design
License: MIT
Source Commit SHA: TBD before implementation
Reuse level: idea_only / reimplemented
```

#### 已阅读

```text
skills/baoyu-design/built-in-skills/make-a-deck.md
```

#### 关键观察

- Presentation 先建立 Story；
- 标题序列可以作为 Storyline 质量检查；
- 视觉需求可以在规划阶段前置，但不等于精确视觉实现。

#### 对本项目的启示

```text
Narrative Strategy
↓
Storyline
↓
Outline
```

以及：

```text
Title Sequence Review
```

#### 不采用

- 不照搬其后续 HTML 设计路线作为本项目 PPT Runtime。

---

### 6. Codex PPT

```text
Repository: qybaihe/codex-ppt
License: MIT
Source Commit SHA: TBD before implementation
Reuse level: idea_only
```

#### 已阅读

```text
SKILL.md
```

#### Stage 1 观察

其工作流中的：

```text
Brief
→ Storyline
→ Storyboard
```

支持本项目引入：

```text
Presentation Brief
→ Narrative Strategy
→ Structured Outline
```

#### Stage 2 / 3 观察

其“设计图通过 QA 后成为可编辑重建的视觉参考”与本项目视觉 Authority 思路相符。

#### 不采用

- 不直接复制其 Storyboard Schema；
- 不把其 Runtime 当成本项目已选依赖。

---

### 7. Slidev

```text
Repository: slidevjs/slidev
License: MIT
Source Commit SHA: TBD before implementation
Reuse level: idea_only
```

#### 已阅读

```text
docs/guide/syntax.md
packages/types/src/types.ts
```

#### 关键观察

```text
Markdown
+
---
+
YAML Frontmatter
```

可以形成轻量、可读、可 Diff 的页面描述。

#### 对本项目的启示

Stage 1 Wireframe 不需要复杂 AST：

```text
Frontmatter
+
正式内容
+
Visual Need
+
ASCII Wireframe
```

#### 不采用

- 不复制 Slidev Parser；
- 不把 Slidev Runtime 作为 PPT Runtime。

---

### 8. PPTist

```text
Repository: pipipi-pikachu/PPTist
License: AGPL-3.0
Source Commit SHA: TBD before implementation
Reuse level: idea_only
```

#### 已阅读

```text
doc/AI_PPT_SCHEMA.md
```

#### 关键观察

其 Schema 已进入：

```text
canvas
left
top
width
height
rotate
element type
background
```

说明这是页面元素实施层，而不是 Stage 1 内容 / 线框层。

#### 对本项目的启示

Stage 1 不应输出精确坐标与视觉实现参数。

#### License 边界

AGPL-3.0 项目默认：

> 只参考思想；未经单独许可证评估，不直接复制或集成代码。

---

## Stage 2 参考项目

### 9. Future Slide

```text
Repository: bytonylee/future-slide
License: TBD in current source set
Source Commit SHA: TBD before implementation
Current status: Candidate
Reuse level: TBD after Benchmark
```

#### 项目级观察

当前 Stage 2 主 Anchor Candidate。

研究关注：

```text
slide-design
gpt-image-slide-plan
gpt-image-slide-prompt
gpt-image-slide-render
```

#### 对本项目最相关

由于本项目 Stage 1 已经负责页面规划，Stage 2 更关注：

```text
slide-design
gpt-image-slide-prompt
gpt-image-slide-render
```

#### 关键研究点

- `DESIGN.md` 式跨页视觉规律；
- Observed / Inferred 分离；
- 逐页结构化 Prompt；
- Page QA；
- 完整 PPT 图片生成。

#### 不采用 / 未决定

- 不直接采用其 Stage 1 Planning；
- 不直接把整个仓库合并进当前 Skill；
- 是否成为 Anchor 取决于 Benchmark；
- 当前不得描述为已选 Runtime。

> License 与具体源码文件路径在正式实施前需要重新核验并锁定 Commit SHA；现有 Stage 2 整理源文件没有完整记录这些信息，因此本文不补写未经来源支持的结论。

---

### 10. SlideSpeak slide-design-skill

```text
Repository: SlideSpeak/slide-design-skill
License: TBD in current source set
Source Commit SHA: TBD before implementation
Current status: Reference
Reuse level: idea_only / possible reimplementation
```

#### 只参考

- Style Intake；
- 构图家族；
- 跨页多样性；
- Prompt 编译；
- 生图前质量 Gate。

#### 明确不采用

- 不引入其完整 TypeScript Engine；
- 不引入其 HTML Renderer 作为本项目 Stage 2 Runtime。

---

### 11. Design Image Studio

```text
Repository: kangarooking/design-image-studio
License: TBD in current source set
Source Commit SHA: TBD before implementation
Current status: Reference
Reuse level: idea_only / possible reimplementation
```

#### 只参考

```text
Structured Design Brief
→ Prompt Compiler
→ Image Provider
```

以及：

- 参考图；
- 重试；
- 成本；
- Fallback；
- 调用日志。

#### 明确不采用

- Benchmark 前不绑定其特定图片 Provider；
- 不合并其完整 Runtime。

---

### 12. Stage 2 Codex PPT 参考角色

Codex PPT 在 Stage 2 不作为第二套 Runtime。

只作为：

```text
Product Flow Reference
```

即：

```text
设计图
↓
QA
↓
用户确认
↓
Approved Design Preview
↓
Editable Reconstruction
```

---

## 13. 项目级映射总结

| 问题 | 外部参考 | 本项目当前用途 |
|---|---|---|
| 用户需求如何标准化 | Codex PPT | Presentation Brief |
| Storyline 怎么建立 | Codex PPT / baoyu-design | Narrative Strategy |
| 每页为什么存在 | PPTAgent | `role / key_message` |
| 内容如何绑定原文 | PPTAgent | `source_refs` |
| 内容与设计如何分开 | Presenton | Authority 隔离 |
| Markdown 线框怎么保存 | Slidev | Markdown + Frontmatter |
| Stage 1 应做到什么粒度 | PPTist | 精确坐标作为边界反例 |
| Stage 2 跨页视觉系统 | Future Slide | Candidate |
| Stage 2 构图与质量规则 | SlideSpeak | Reference |
| Prompt / Provider 如何分层 | Design Image Studio | Reference |
| 设计图如何成为 Stage 3 视觉目标 | Codex PPT | Product-flow reference |

---

## 14. 实施前源码冻结清单

任何外部源码进入 Implementation Plan 前，必须补齐：

```yaml
source_project:
source_commit:
source_file:
observed_behavior:
planned_local_behavior:
reuse_type:
license:
copyright:
notice_required:
```

---

## 15. 当前证据结论

Stage 1：

> 多项目思想已经足够支持本项目自行实现轻量 Contract，不需要 Vendor 外部 Runtime。

Stage 2：

> Future Slide 只是 Anchor Candidate；其他项目只是参考。真正采用什么必须由 Benchmark 决定。

因此当前最重要原则：

```text
先 Benchmark
↓
再选 Anchor / Model
↓
再决定是否移植代码
```
