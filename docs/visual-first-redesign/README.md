# 视觉优先三阶段重构：研究文档导航

> **Status**：Research / Proposal（研究与提案）
> **Document type**：Navigation & Status（导航与状态）
> **Authority**：非运行权威，仅说明研究状态、阅读顺序和文档边界
> **Current runtime relationship**：不改变当前正式产品、Runtime、入口或 Accepted ADR
> **Depends on**：当前 [Accepted ADR / DECISIONS](../../DECISIONS.md)、正式 [SKILL.md](../../content-to-editable-ppt/SKILL.md)、当前 Runtime 契约
> **Next decision gate**：完成 Stage 2 Benchmark；只有 `Passed` 才允许进入新 ADR
> **Last updated**：2026-08-28

---

## 1. 本目录记录什么

本目录只记录 `content-to-editable-ppt-skill` 的视觉优先三阶段目标方案。

目标流程：

```text
Stage 1
内容、大纲、Markdown 线框
↓
第一次正式确认：内容权威

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

- 第一次正式确认冻结内容与页面组织；
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
   Stage 2 候选技术、Benchmark、决策门禁和当前结论。

4. [`references/external-project-and-source-review.md`](references/external-project-and-source-review.md)
   外部 GitHub 项目、源码与许可证证据。

---

## 4. 当前阶段不再新增目标架构文档

原整理方案曾计划的：

```text
05-target-architecture-and-migration.md
```

当前不继续维护。

原因：

- Stage 2 Anchor 尚未通过 Benchmark；
- 图片模型尚未冻结；
- Visual Designer / Prompt Compiler / Reviewer 仍有未验证假设；
- 迁移和 `Main Mode / Fast Mode` 最终定位应该由未来新 ADR 决定。

因此当前保持：

```text
研究
↓
Benchmark
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

等 Stage 2 真正通过后，再新增：

```text
04-stage2-design.md
```

记录最终冻结的 Stage 2 设计。

---

## 5. 与历史文档的关系

仓库中的旧 Architecture、Specification、Contract、Testing 和 `docs/plans/p1`～`p5` 文档记录精简前的 P1～P5 多页体系，其中部分概念与本目录重叠，但已明确标记为历史或由 ADR-043 取代。

本目录：

- 是后续产品改造的统一研究入口；
- 不恢复旧 P1～P5 Runtime、State、Gate、Evidence 或 Schema；
- 不删除 Accepted ADR 或历史决策；
- 不把旧 `Approved Design Preview` Artifact 合同自动恢复为当前合同；本文中的同名术语仅表示未来目标中的“经第二次正式确认的全套设计图”；
- 不提交本次整理所依据的下载目录原稿和重复草稿。
