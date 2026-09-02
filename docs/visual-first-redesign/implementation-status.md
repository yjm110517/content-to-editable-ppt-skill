# Visual-first 实施状态与接力说明

> **状态日期**：2026-09-02  
> **实现分支**：`codex/visual-first-code-refactor`  
> **远端状态**：已推送至 `origin/codex/visual-first-code-refactor`  
> **最新完成提交**：`aaa59b8`  
> **正式运行权威**：仍以 Accepted ADR、`SKILL.md`、`run.py` 和 `run_pipeline.py` 为准

## 1. 当前结论

Visual-first P1～P8 改造路线已经完成 **P1、P2、P3**，下一阶段是 **P4：Native Chart / Native Table / SVG 与 Builder、QA 能力补齐**。

当前实现已经证明：Stage 1 / Stage 2 Authority 可以确定性投影为单页 Reconstruction Handoff；Fresh Layout Planner 可以基于 Handoff 输出 PLAN Candidate；Finalizer 会完成 Runtime Canonicalization，并通过 P1 Compiler 驱动现有 PowerPoint Runtime。

这些代码仍位于功能分支，尚未通过新 ADR 和 P8 切换为正式 Skill 主路径。

## 2. 已完成阶段

| 阶段 | 已落地能力 | 主要提交 |
|---|---|---|
| P1 | Canonical Reconstruction Plan Schema、纯 Compiler、CLI Adapter、normalized geometry、Authority text、Raster crop/aspect Gate | `eeb2133`、`c6a5bb7` |
| P2 | Stage 1 Authority、Stage 2 Handoff、raw SHA-256 绑定、路径安全、单页 Reconstruction Handoff Materializer | `b42cffe`、`a277b6b` |
| P3 | Planner Initial 切换到 Handoff、PLAN/BLOCK 1.4、Stable ID/Topology Gate、Runtime 尺寸规范化、P1 Core 复用 | `4952b35`、`8efe182`、`aaa59b8` |

P3 当前支持：

- `native_text`、`native_shape`、`native_connector`、`raster_asset`；
- Fresh Planner Initial 调用包及输入 Hash 绑定；
- Candidate Validation → Runtime Canonicalization → Canonical Validation；
- Chart/Table 的对象级 `unsupported_reconstruction` BLOCK；
- 同一 Planner Response 与 Authority 输入产生字节一致的派生 Artifact。

## 3. 验收证据

完整 Runtime 回归：`115` 项通过，`1` 项默认跳过；显式 Windows + Microsoft PowerPoint Smoke 已通过。

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

- **P4**：Native Chart、Native Table、SVG、Builder 与结构/可编辑性 QA；
- **P5**：Canonical Revision Patch 与局部锁定修订；
- **P6**：确定性 Review Context、Fresh Visual Reviewer、四级判定；
- **P7**：Accepted Page Plan、资产冻结、Final Deck Assembly；
- **P8**：新 ADR、`SKILL.md`、主 Orchestrator 与正式用户路径切换。

在 P4 完成前，Chart、Table、SVG 只属于已知但未支持的 Representation，禁止降级为截图。

## 5. 正式产品边界

当前用户可依赖的正式路径没有变化：

- 多页 Content-to-Deck：`content-to-editable-ppt/scripts/run.py`；
- 单张参考图重建：`content-to-editable-ppt/scripts/run_pipeline.py`；
- Visual-first P1～P3：仅在 `codex/visual-first-code-refactor` 上验证，不应描述为已发布功能。

## 6. 下一位开发者从这里继续

1. 切换并同步 `codex/visual-first-code-refactor`；
2. 阅读本文件、[`visual-first-code-refactor-plan.md`](visual-first-code-refactor-plan.md) 第七节和 [`04-stage3-guidance.md`](04-stage3-guidance.md) 的 Native Chart/Table Policy；
3. 从 P4 实施计划开始，不提前修改 Reviewer、Accepted Page Plan 或正式 `SKILL.md`；
4. 改动后执行：

```powershell
python -m unittest discover -s tests/runtime -p "test_*.py"
git diff --check
```

涉及 PowerPoint Native 对象时，必须在 Windows + Microsoft PowerPoint 环境保存构建、渲染和结构 QA Evidence。
