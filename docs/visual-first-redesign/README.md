# 视觉优先三阶段重构：研究文档导航

> **Status**：Final Guidance + Research / Benchmark Pending（目标指导已确认，研究与 Benchmark 待执行）
> **Document type**：Navigation & Status（导航与状态）
> **Authority**：非运行权威，仅说明研究状态、阅读顺序和文档边界
> **Current runtime relationship**：不改变当前正式产品、Runtime、入口或 Accepted ADR
> **Depends on**：当前 [Accepted ADR / DECISIONS](../../DECISIONS.md)、正式 [SKILL.md](../../content-to-editable-ppt/SKILL.md)、当前 Runtime 契约
> **Next decision gate**：完成 Stage 2 Benchmark；只有 `Passed` 才允许进入新 ADR
> **Last updated**：2026-08-31

---

## 1. 本目录记录什么

本目录只记录 `content-to-editable-ppt-skill` 的视觉优先三阶段目标方案。

目标流程：

```text
Stage 1
内容、大纲、Markdown 线框
+ 机器可读语义结构
+ 必要结构化数据
↓
第一次正式确认：内容 / 结构 / 数据权威

Stage 2
视觉系统
↓
代表性视觉页
↓
Representative Design Gate
↓
全套设计图
↓
第二次正式确认：视觉权威

Stage 3
已确认的全套设计图
↓
可编辑 PPT
```

其中：

- 第一次正式确认冻结正式内容、页面结构 / 拓扑及必要结构化数据；
- `Representative Design Gate` 只是 Stage 2 内部 Fail-fast 校准点，不是正式 Approval；
- 只有全套设计图完成第二次正式确认后，才成为 `Approved Design Preview`；
- Stage 3 负责高保真重建，不重新设计。

---

## 2. 当前运行权威没有变化

当前正式权威顺序：

```text
Accepted ADR / DECISIONS
↓
正式 SKILL.md / Runtime Contract
↓
当前 Runtime 实现与行为
↓
README 等用户说明
↓
目标设计与研究文档
```

因此本目录：

- 不修改 Runtime；
- 不修改 Schema；
- 不修改 Agent；
- 不修改 Accepted ADR；
- 不把视觉优先路线宣称为已实现；
- 不把当前 `run.py` 提前称为 `Fast Mode`。

本文档落库时（2026-08-28）的当前实现快照是：

- ADR-042、ADR-043 均为 Accepted；
- 多页正式入口是 [`scripts/run.py`](../../content-to-editable-ppt/scripts/run.py)，消费一次确认后的 [`deck-build-request.json`](../../content-to-editable-ppt/schemas/deck-build-request.schema.json)，直接执行构建、PowerPoint 渲染、Roundtrip、结构 QA 和原子交付；
- 单页图片重建继续使用独立 [`scripts/run_pipeline.py`](../../content-to-editable-ppt/scripts/run_pipeline.py)，并保留 Planner、Visual Reviewer、Recovery、Review Gate、Warning Acceptance、Delivery Decision 和七文件交付契约；
- 旧 P1～P5 多页 Runtime 已删除。

> 后续更新本目录时，应以最新 `main` 的 ADR / DECISIONS 为准重新核验当前编号、状态和 `supersedes` / `preserves` 关系。

---

## 3. 阅读顺序

1. [`01-product-requirements.md`](01-product-requirements.md)
   产品最终要解决什么。

2. [`02-stage1-design.md`](02-stage1-design.md)
   Stage 1 最终目标设计。

3. [`03-stage2-research-and-decision.md`](03-stage2-research-and-decision.md)
   Stage 2 已确认目标指导、真实图片验证、Benchmark、决策门禁和当前结论。

4. [`04-stage3-guidance.md`](04-stage3-guidance.md)
   Stage 3 的总体 Pre-ADR Target Guidance：定义重建职责、Authority、跨阶段 Handoff、Native Chart / Table、Accepted Page Plan、Shared Builder 与最终 QA；不构成 Runtime Implementation Authority。

5. [`layout-planner-prompt-contract.md`](layout-planner-prompt-contract.md)
   布局规划代理任务合同：定义输入、Authority、初次规划、定向修订、视觉位置对齐与重建方式决策。

6. [`visual-reviewer-prompt-contract.md`](visual-reviewer-prompt-contract.md)
   视觉审核代理任务合同：定义独立审核上下文、视觉审核维度、四级判定结果与定向修订接口。

7. [`stage3-reconstruction-plan-contract.md`](stage3-reconstruction-plan-contract.md)
   Stage 3 统一重建计划合同：定义 Canonical Reconstruction Plan、Revision Patch、Accepted Page Plan 以及与确定性 Runtime 的接口边界。

8. [`visual-first-code-refactor-plan.md`](visual-first-code-refactor-plan.md)
   Visual-first 的 P1～P8 代码改造路线：从 Canonical Reconstruction Plan 基础设施逐步推进到正式 Skill 主流程切换。

9. [`references/external-project-and-source-review.md`](references/external-project-and-source-review.md)
   外部 GitHub 项目、源码与许可证证据。

### Stage 3 文档职责边界

- `04-stage3-guidance.md`：Stage 3 总体设计与跨阶段规则；
- `layout-planner-prompt-contract.md`：Layout Planner 专属任务规则；
- `visual-reviewer-prompt-contract.md`：Visual Reviewer 专属审核规则；
- `stage3-reconstruction-plan-contract.md`：Canonical Reconstruction Plan、Revision Patch 与 Accepted Page Plan 的专属 Artifact 合同。

总体 Guidance 不重复复制三个 Contract 的完整细节；专属规则以对应 Contract 为准。

---

## 4. Agent 角色

### 宿主代理

宿主代理是整个 Skill 的执行与编排主体，负责：

- Stage 1 全流程；
- Stage 2 视觉设计细化与图片生成流程编排；
- Stage 3 专业 Agent、确定性 Runtime 与用户确认流程的调度。

Stage 1 不新增大纲规划代理、线稿规划代理或 Stage 1 审核代理；Stage 2 v1 不新增独立视觉设计代理。宿主代理不是被调用的专业子代理。

### Stage 3 专业代理

Stage 3 v1 只保留两个独立专业 Agent：

1. **布局规划代理（Layout Planner Agent）**：已知对象视觉位置对齐与重建方式决策；第一版一次调用完成这两个逻辑任务。
2. **视觉审核代理（Visual Reviewer Agent）**：独立比较最终设计图与 PowerPoint 实际渲染结果，并与布局规划代理保持独立上下文。

### 非 Agent 组件

| 组件 | 类型 / 职责 |
|---|---|
| 图片生成模型 | 图片生成工具，不是 Agent |
| Prompt Compiler | 确定性程序，编译 Prompt，不设计或改写内容 |
| Handoff / Context Compiler | 确定性程序，整理已结构化的上游事实，不重新理解自由文本 |
| PPT Builder / Shared Builder | 确定性程序，构建单页或整套 PPT |
| Structural QA / Deck QA | 确定性程序，验证编辑性、结构和交付完整性 |
| PowerPoint Renderer | PowerPoint 运行环境，用于渲染、打开与 Roundtrip 检查 |
| 确定性 Patch / Recovery 工具 | 确定性程序，不是 Agent |

---

## 5. Benchmark 前的文档边界

Benchmark 前允许继续维护 Stage 1～3 的 **Target Guidance / Pre-ADR Working Guidance**，用于把未来三阶段路线的职责、Authority、跨阶段 Handoff 和关键设计决策记录清楚。

但这些 Guidance：

- 不修改 Runtime；
- 不修改当前正式 Schema；
- 不修改当前 Agent；
- 不修改 Accepted ADR；
- 不构成 Runtime Implementation Plan；
- 不把 Visual-first 路线宣称为已实现或已 Accepted。

原整理方案曾计划的：

```text
05-target-architecture-and-migration.md
```

当前不继续维护。

原因：

- Stage 2 尚未通过真实图片 Benchmark；
- 图片模型、Provider、自动视觉审核实现和通过阈值尚未冻结；
- 不在 Benchmark 前编写 Runtime Implementation Plan 或改写当前入口；
- 迁移和 `Main Mode / Fast Mode` 最终定位应由未来新 ADR 决定。

因此正式决策链仍保持：

```text
研究 / Target Guidance
↓
Stage 2 Benchmark
↓
Decision
↓
Passed？
├─ No → 继续研究
└─ Yes → 起草新 ADR
          ↓
        Accepted？
        ├─ No → 保持当前产品
        └─ Yes → 编写 Implementation Plan
```

Stage 2 Benchmark Passed 后，再根据证据决定是否新增 / 冻结正式 Stage 2 Design 文档及后续 Implementation 文档。

---

## 6. 与历史文档的关系

仓库中的旧 Architecture、Specification、Contract、Testing 和 `docs/plans/p1`～`p5` 文档记录精简前的 P1～P5 多页体系，其中部分概念与本目录重叠，但已明确标记为历史或由 ADR-043 取代。

本目录：

- 是后续产品改造的统一研究入口；
- 不恢复旧 P1～P5 Runtime、State、Gate、Evidence 或 Schema；
- 不删除 Accepted ADR 或历史决策；
- 不把旧 `Approved Design Preview` Artifact 合同自动恢复为当前合同；本文中的同名术语仅表示未来目标中的“经第二次正式确认的全套设计图”；
- 不提交本次整理所依据的下载目录原稿和重复草稿。
