# Visual-first 实施状态与接力说明

> **状态日期**：2026-09-04
> **实现分支**：`codex/visual-first-code-refactor`  
> **远端状态**：本地领先 `origin/codex/visual-first-code-refactor` 3 个提交
> **最新完成提交**：`0227011`
> **正式运行权威**：仍以 Accepted ADR、`SKILL.md`、`run.py` 和 `run_pipeline.py` 为准

## 1. 当前结论

Visual-first P1～P8 改造路线已经完成 **P1、P2、P3、P4**；下一阶段是 **P5：Canonical Revision Patch 与局部锁定修订**。

当前实现已经证明：Stage 1 / Stage 2 Authority 可以确定性投影为单页 Reconstruction Handoff；Fresh Layout Planner 可以基于 Handoff 输出 PLAN Candidate；Finalizer 会完成 Runtime Canonicalization，并通过 P1 Compiler 驱动现有 PowerPoint Runtime。

P4 已以真实 Fresh Planner、Microsoft PowerPoint 和 SaveAs Roundtrip 完成 Native Chart/Table 验收。代码仍位于功能分支，尚未通过新 ADR 和 P8 切换为正式 Skill 主路径。

## 2. 已完成阶段

| 阶段 | 已落地能力 | 主要提交 |
|---|---|---|
| P1 | Canonical Reconstruction Plan Schema、纯 Compiler、CLI Adapter、normalized geometry、Authority text、Raster crop/aspect Gate | `eeb2133`、`c6a5bb7` |
| P2 | Stage 1 Authority、Stage 2 Handoff、raw SHA-256 绑定、路径安全、单页 Reconstruction Handoff Materializer | `b42cffe`、`a277b6b` |
| P3 | Planner Initial 切换到 Handoff、PLAN/BLOCK 1.4、Stable ID/Topology Gate、Runtime 尺寸规范化、P1 Core 复用 | `4952b35`、`8efe182`、`aaa59b8` |
| P4 | Native Chart/Table Builder、原生对象与数据结构 QA、图表数据标签格式保留、Fresh Planner Live Validation 与 PowerPoint Roundtrip Evidence | `59ba4eb`、`b599c9a`、`d8e3ec9`、`0227011` |

P3 当前支持：

- `native_text`、`native_shape`、`native_connector`、`raster_asset`；
- Fresh Planner Initial 调用包及输入 Hash 绑定；
- Candidate Validation → Runtime Canonicalization → Canonical Validation；
- Chart/Table 的对象级 `unsupported_reconstruction` BLOCK；
- 同一 Planner Response 与 Authority 输入产生字节一致的派生 Artifact。

## 3. 验收证据

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

- **P5**：Canonical Revision Patch 与局部锁定修订（**READY**）；
- **P6**：确定性 Review Context、Fresh Visual Reviewer、四级判定；
- **P7**：Accepted Page Plan、资产冻结、Final Deck Assembly；
- **P8**：新 ADR、`SKILL.md`、主 Orchestrator 与正式用户路径切换。

P4 的关闭范围是 Native Chart/Table Live Validation。既有 SVG/Crop 能力由完整 Runtime 回归继承，本阶段未新增该部分实现。P5 之前不得提前修改 Reviewer、Accepted Page Plan、正式 `SKILL.md` 或主 Orchestrator。

## 5. 正式产品边界

当前用户可依赖的正式路径没有变化：

- 多页 Content-to-Deck：`content-to-editable-ppt/scripts/run.py`；
- 单张参考图重建：`content-to-editable-ppt/scripts/run_pipeline.py`；
- Visual-first P1～P4：仅在 `codex/visual-first-code-refactor` 上验证，不应描述为已发布功能。

## 6. 下一位开发者从 P5 开始

1. 切换并同步 `codex/visual-first-code-refactor`；
2. 阅读本文件、[`visual-first-code-refactor-plan.md`](visual-first-code-refactor-plan.md) 中的 P5 计划，以及已冻结的 [`../../reports/p4/evidence/p4-native-data-objects/evidence-summary.json`](../../reports/p4/evidence/p4-native-data-objects/evidence-summary.json)；
3. 从 P5 Canonical Revision Patch 开始，不提前修改 Reviewer、Accepted Page Plan 或正式 `SKILL.md`；
4. 改动后执行：

```powershell
python -m unittest discover -s tests/runtime -p "test_*.py"
git diff --check
```

涉及 PowerPoint Native 对象时，必须在 Windows + Microsoft PowerPoint 环境保存构建、渲染和结构 QA Evidence。
