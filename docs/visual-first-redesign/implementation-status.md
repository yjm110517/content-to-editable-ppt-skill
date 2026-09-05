# Visual-first 实施状态与接力说明

> **状态日期**：2026-09-05
> **实现分支**：`codex/visual-first-code-refactor`  
> **远端状态**：本地领先 `origin/codex/visual-first-code-refactor` 6 个提交
> **最新验收 Evidence 提交**：`db92a5d`
> **正式运行权威**：仍以 Accepted ADR、`SKILL.md`、`run.py` 和 `run_pipeline.py` 为准

## 1. 当前结论

Visual-first P1～P8 改造路线已经完成 **P1、P2、P3、P4、P5**；下一阶段是 **P6：确定性 Review Context 与 Fresh Visual Reviewer**。

当前实现已经证明：Stage 1 / Stage 2 Authority 可以确定性投影为单页 Reconstruction Handoff；Fresh Layout Planner 可以基于 Handoff 输出 PLAN Candidate；Finalizer 会完成 Runtime Canonicalization，并通过 P1 Compiler 驱动现有 PowerPoint Runtime。

P4 已以真实 Fresh Planner、Microsoft PowerPoint 和 SaveAs Roundtrip 完成 Native Chart/Table 验收。代码仍位于功能分支，尚未通过新 ADR 和 P8 切换为正式 Skill 主路径。

P5 已以真实 Fresh Revision Planner、Call Record 1.4 宿主证据、Canonical Patch Finalizer、Atomic Apply 和 Microsoft PowerPoint 完成局部修订验收。采样参数未由宿主暴露，Evidence 如实记录为 unavailable；Fresh Context、完整 10 项输入、图片投递与原始 Response Gate 均保持严格。

## 2. 已完成阶段

| 阶段 | 已落地能力 | 主要提交 |
|---|---|---|
| P1 | Canonical Reconstruction Plan Schema、纯 Compiler、CLI Adapter、normalized geometry、Authority text、Raster crop/aspect Gate | `eeb2133`、`c6a5bb7` |
| P2 | Stage 1 Authority、Stage 2 Handoff、raw SHA-256 绑定、路径安全、单页 Reconstruction Handoff Materializer | `b42cffe`、`a277b6b` |
| P3 | Planner Initial 切换到 Handoff、PLAN/BLOCK 1.4、Stable ID/Topology Gate、Runtime 尺寸规范化、P1 Core 复用 | `4952b35`、`8efe182`、`aaa59b8` |
| P4 | Native Chart/Table Builder、原生对象与数据结构 QA、图表数据标签格式保留、Fresh Planner Live Validation 与 PowerPoint Roundtrip Evidence | `59ba4eb`、`b599c9a`、`d8e3ec9`、`0227011` |
| P5 | Canonical Revision Patch、Target/Linked Scope Lock、真实 Deep Diff、Atomic Apply、宿主调用证据与 Fresh Revision Live Validation | `0854a24`、`2549f6e`、`ecf8f63`、`ad7d963`、`db92a5d` |

P3 当前支持：

- `native_text`、`native_shape`、`native_connector`、`raster_asset`；
- Fresh Planner Initial 调用包及输入 Hash 绑定；
- Candidate Validation → Runtime Canonicalization → Canonical Validation；
- Chart/Table 的对象级 `unsupported_reconstruction` BLOCK；
- 同一 Planner Response 与 Authority 输入产生字节一致的派生 Artifact。

## 3. 验收证据

P5 完整 Runtime 回归：`159` 项总计，`156` 项通过、`3` 项按设计跳过；P1、P4、P5 三项显式 Windows + Microsoft PowerPoint Smoke 均通过且未跳过。

固定真实修订 `P5-LIVE-01` 已完成：Fresh Planner 将 `card-02.geometry.y` 从 `0.50` 调整为 `0.35`；Finalizer 和 Atomic Apply 生成 Plan `1.2` iteration `2`，`title-object`、`card-01`、`connector-01`、`hero` Deep Equal，`unauthorized_changes=[]`。新版 PowerPoint Build、Render 和 Structural QA 通过，`fallback_used=false`、Hard Failure 为零。

最终证据入口：[`../../reports/p5/evidence/p5-canonical-revision-patch/evidence-summary.json`](../../reports/p5/evidence/p5-canonical-revision-patch/evidence-summary.json)。两次真实失败调用分别因旧 Response Schema 漏项和 Planner iteration 身份错误保存在 `attempts/`，均未计为 PASS。

P4 完整 Runtime 回归：`124` 项通过，`2` 项按设计跳过；两项显式 Windows + Microsoft PowerPoint Smoke 已通过。

固定真实页面 `P4-LIVE-01｜实验结果概览` 已完成：

```text
clean d8e3ec9 worktree
→ request.json + Stage 1 Authority + Stage 2 Handoff
→ P2 Materializer
→ Fresh Planner（Role 1.5.1，严格 7 项输入）
→ 未修改的 raw_response.json
→ Finalizer
→ Canonical Reconstruction Plan
→ Microsoft PowerPoint
→ Native Chart/Table QA PASS（0 Hard Failure）
→ SaveAs Roundtrip
→ 规范化 Chart/Table Signature 一致
```

最终证据入口：[`../../reports/p4/evidence/p4-native-data-objects/evidence-summary.json`](../../reports/p4/evidence/p4-native-data-objects/evidence-summary.json)。首次因图表数据标签格式未保留而失败的原始 Planner 材料保存在该目录的 `attempts/` 下；修复后从新的 Fresh Context 重跑通过。

固定真实页面 `P3-LIVE-01｜AI 学习闭环` 已完成：

```text
Fresh Layout Planner
→ 未修改的 Planner Response
→ Finalizer
→ Canonical Plan
→ Existing Pipeline
→ PowerPoint
→ Render
→ Structural QA PASS
```

`P3-BLOCK-01` 也已确认 `chart-01` 返回对象级 `unsupported_reconstruction`，退出成功且不创建 iteration。

证据入口：[`../../reports/p3/evidence/p3-live-planner-smoke/evidence-summary.json`](../../reports/p3/evidence/p3-live-planner-smoke/evidence-summary.json)。

## 4. 尚未完成

- **P6**：确定性 Review Context、Fresh Visual Reviewer、四级判定；
- **P7**：Accepted Page Plan、资产冻结、Final Deck Assembly；
- **P8**：新 ADR、`SKILL.md`、主 Orchestrator 与正式用户路径切换。

P5 的关闭范围是 Canonical Revision Patch、局部锁定、Atomic Apply 与 Fresh Revision Live Validation。本阶段未修改 Reviewer、Accepted Page Plan、正式 `SKILL.md` 或主 Orchestrator；这些后续边界仍由 P6～P8 分阶段处理。

## 5. 正式产品边界

当前用户可依赖的正式路径没有变化：

- 多页 Content-to-Deck：`content-to-editable-ppt/scripts/run.py`；
- 单张参考图重建：`content-to-editable-ppt/scripts/run_pipeline.py`；
- Visual-first P1～P5：仅在 `codex/visual-first-code-refactor` 上验证，不应描述为已发布功能。

## 6. 下一位开发者从 P6 开始

1. 切换并同步 `codex/visual-first-code-refactor`；
2. 阅读本文件、[`visual-first-code-refactor-plan.md`](visual-first-code-refactor-plan.md) 中的 P6 计划，以及已冻结的 [`../../reports/p5/evidence/p5-canonical-revision-patch/evidence-summary.json`](../../reports/p5/evidence/p5-canonical-revision-patch/evidence-summary.json)；
3. 从 P6 确定性 Review Context 与 Fresh Visual Reviewer 开始，不提前实施 Accepted Page Plan、正式 `SKILL.md` 或主 Orchestrator 切换；
4. 改动后执行：

```powershell
python -m unittest discover -s tests/runtime -p "test_*.py"
git diff --check
```

涉及 PowerPoint Native 对象时，必须在 Windows + Microsoft PowerPoint 环境保存构建、渲染和结构 QA Evidence。
