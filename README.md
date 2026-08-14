# Content to Editable PPT Skill

`content-to-editable-ppt-skill` 的目标是把主题、文档或大纲转换为多页、可编辑的 PowerPoint 演示文稿。

## 当前状态

本仓库已完成 P0 Baseline Freeze、P0.5 Runtime Hardening、P1 Host Content Planning、P2 Markdown Wireframe 和 P3.1 Tabler Core。正式 P3.1 回退链正在调整：生产路径只允许准确匹配的 Tabler SVG，或进入等待 Approved Design Preview 的 Raster Handoff。P3.2 Visual System / Prompt Package 尚未实现，正式页面视觉设计和多页 PPT 生成仍不可用。

当前可执行流程为“材料 → 待确认大纲 → 冻结页面文字 → Markdown 文字线稿”和“参考图片 → 可编辑单页 PPT”。以下能力尚未实现，不能视为当前承诺：

- 最终页面视觉设计和设计图片生成；
- 从冻结页面内容自动生成完整多页 PPT；
- 跨页主题、字体和版式一致性；
- 图表、引用和来源管理；
- 面向完整演示文稿的多页视觉审核。

最终产品目标是先生成高质量图片版页面并由用户确认，再以 Approved Design Preview 为视觉权威、以 P1 内容为文字权威，高保真重建可编辑 PowerPoint。当前代码尚未完成这条多页链路。

## 计划中的调用接口

Skill 名称和安装目录已经确定：

```text
$content-to-editable-ppt
content-to-editable-ppt/
```

该调用名可以用于 P1 内容规划和继承的单页重建 Runtime，但不应对外宣称已经支持完整的内容到多页 PPT 工作流。

## 当前仓库结构

```text
content-to-editable-ppt-skill/
├─ README.md
├─ DECISIONS.md
├─ LICENSE
├─ NOTICE
├─ baseline/
│  ├─ manifest.json
│  ├─ baseline-report.md
│  └─ cases/B01...B06/
├─ docs/
│  ├─ architecture/v2.0/ ... v2.3/
│  ├─ contracts/v1.0/ ... v1.3/
│  ├─ development/v1.4/
│  ├─ runtime/
│  │  ├─ v1.0/
│  │  └─ v1.1/
│  ├─ specifications/
│  │  ├─ v1.0/
│  │  ├─ v1.1/
│  │  ├─ v1.2/
│  │  └─ v1.3/
│  └─ testing/v1.0/ ... v1.3/
├─ tools/baseline/
└─ content-to-editable-ppt/
   ├─ SKILL.md
   ├─ agents/
   ├─ references/
   ├─ schemas/
   └─ scripts/
```

## 已继承的运行时能力

- 使用 PptxGenJS 构建原生文本、形状、线条和图片资产；
- 裁切、打包和校验图片或 SVG 资产；
- 审计字体并通过 PowerPoint 渲染结果；
- 检查对象、媒体、越界和可编辑性；
- 分离布局规划与独立视觉审核角色；
- 使用确定性 Schema、运行状态和交付门槛。

## 开发文档

### 权威层级

1. [总体架构与开发计划 v2.3](docs/architecture/v2.3/overall-architecture-and-development-plan.md) 决定当前阶段、视觉 Authority、Prompt Package、资产回退和受约束重建边界。
2. [Architecture Decision Log](DECISIONS.md) 记录已经接受的关键决策、原因、后果和变更规则。
3. 对应产品、Runtime 和 Agent 专项规范定义实现要求。
4. [Artifact、State 与权威数据契约 v1.3](docs/contracts/v1.3/artifact-state-authority-contract.md) 定义 Content、Layout、Asset、Prompt、Preview 和 Reconstruction Authority。
5. [测试与验收计划 v1.3](docs/testing/v1.3/test-and-acceptance-plan.md) 定义生产回退、P3.2、P3.3、P4 和 P5 Gate。

### 当前产品规格（v1.5）

- [需求规格说明](docs/specifications/v1.5/requirements.md)
- [功能规格说明](docs/specifications/v1.5/functional-specification.md)
- [Agent 职责与交接契约](docs/specifications/v1.5/agent-handoff-contract.md)
- [非功能需求与质量指标](docs/specifications/v1.5/non-functional-requirements.md)

### Runtime 与实现规范

- [单页 Runtime 执行与错误恢复规范 v1.1](docs/runtime/v1.1/single-slide-runtime-and-error-recovery.md)
- [运行环境安装与引导规范 v1.1](docs/runtime/v1.1/environment-setup-and-bootstrap.md)
- [增量开发文档 v1.4](docs/development/v1.4/development-guide.md)

旧规格、旧架构、旧 Artifact 契约、旧测试计划和 SVG P2 计划保留为历史基线。新开发和验收以产品规格 v1.5、Runtime v1.1、总体架构 v2.3、Artifact 契约 v1.3 和测试计划 v1.3 为准。

这些文档是开发和验收的完整权威规格。Skill 运行目录中的 `SKILL.md`、`references/`、`agents/` 和 `schemas/` 只保留实际执行所需的精简规则与机器可验证契约。

## P0 Baseline

[P0 Baseline Freeze Report](baseline/baseline-report.md) 记录 6 个 Case 的最终迭代、Structural QA、Visual Reviewer、调用次数、技术重试和已知问题。冻结结果不等同于像素级 Golden，也不表示当前视觉缺陷已经修复。

开发用入口：

```powershell
.\tools\baseline\baseline.ps1 -Action Prepare -Case B01 -NodePath <node.exe> -PythonPath <python.exe>
.\tools\baseline\baseline.ps1 -Action Capture -Case B01 -PythonPath <python.exe>
.\tools\baseline\baseline.ps1 -Action Verify -All -PythonPath <python.exe>
```

## P1 Content Planning

P1 开发入口：

```powershell
python .\content-to-editable-ppt\scripts\manage_content_plan.py init --task-id <id> --deck-id <id> --state <state.json>
python .\content-to-editable-ppt\scripts\manage_content_plan.py route --state <state.json> --route <route.json>
python .\content-to-editable-ppt\scripts\manage_content_plan.py resolve-materials --state <state.json> --materials <materials.json>
python .\content-to-editable-ppt\scripts\manage_content_plan.py submit-candidate --state <state.json> --candidate <candidate.json> --deck-request <request.json> --materials <materials.json>
python .\content-to-editable-ppt\scripts\manage_content_plan.py request-confirmation --state <state.json>
python .\content-to-editable-ppt\scripts\manage_content_plan.py record-outline-response --state <state.json> --candidate <candidate.json> --confirmation <confirmation.json> --approved-output <approved.json>
python .\content-to-editable-ppt\scripts\manage_content_plan.py project-slide-content --state <state.json> --outline <approved.json> --output-dir <content-dir>
```

[P1 Gate 报告](reports/p1/p1-content-planning-gate.json) 记录 D03、D05、D08、Canonical Hash、确认与投影验收结果。

## P2 Markdown Wireframe

P2 的正式目标是由 Host 逐页生成 `deck-wireframe.md`，同时体现完整 Approved Content、等宽字符布局草稿和布局说明；极薄的 `wireframe-manifest.json` 只绑定身份、Hash、页序、Content Ref、Revision 和状态。

Markdown Binder、极薄 Manifest、Validator、受限 Correction、不可变 Revision、聊天预览、反馈路由和新 Gate 均已实现。P2 不生成 SVG、PNG 或 PPTX，也不承担最终视觉设计。

[Markdown P2 Gate 报告](reports/p2/p2-markdown-wireframe-gate.json) 记录 D03、D05、D08 的 Authority、完整性和确定性验收。[旧 P2 Gate 报告](reports/p2/p2-wireframe-gate.json) 与已合并 PR #12–#16 只作为 SVG 历史实现证据。

## P3.1 Asset Resolution

P3.1 Tabler Core 使用固定的 Tabler Outline 3.46.0、不可变 Resolution Record、真实 SVG Sanitizer、Asset Manifest 1.4 和 Consumption Contract。它已经证明同一 Sanitized SVG Source 能被 synthetic Preview Compositor 与 PPT Runtime 消费，但不产生正式 Design Preview。

[P3.1 Gate 报告](reports/p3/p3-icon-resolution-gate.json) 记录历史 Existing、Composition、Programmatic、Raster Handoff、resvg/Pillow consumption 和 PowerPoint Render Smoke。按照 ADR-039，Composition 和 Programmatic 仅作为历史实验能力；正式生产链调整为“准确 Tabler SVG，或 Raster Handoff Pending 后从 Approved Design Preview 提取独立 PNG”。

## 目标视觉链路

```text
P1 Approved Content
→ P2 Markdown Wireframe
→ P2.1 Visual Placeholder
→ P3.1 Resolved Standard Assets
→ P3.2 Deck Visual System + Locked Prompt Package
→ Approved Style Anchor
→ P3.3 Approved Design Previews
→ P4 Constrained Reconstruction
→ P5 Editable Deck + Final Visual Gate
```

所有 Deck 必须先确认 Style Anchor。每页 Prompt 由确定性程序注入内容、线稿和资产；默认每页只生成一次 Initial Design，禁止自动重生成。全页执行确定性 QA，Reviewer 只处理异常页并执行一次 Deck 一致性审核。

## 下一阶段

下一步先完成 P3.1 Production Fallback Cutover，再实施 [P3 视觉设计与受约束重建计划](docs/plans/p3/visual-design-and-constrained-reconstruction-plan.md)。当前不能宣称 Prompt Compiler、Approved Design Preview、完整多页 PowerPoint、Deck Assembly 或最终多页审核已经完成。

## 开发验证

Skill 基础结构可使用 Codex 的 `skill-creator` 校验器检查：

```powershell
python <resolved-skill-creator>\scripts\quick_validate.py .\content-to-editable-ppt
```

Node.js 运行时要求 Node.js 20 或更高版本。依赖声明位于 `content-to-editable-ppt/scripts/package.json`，Python 依赖声明位于 `content-to-editable-ppt/scripts/requirements.txt`。

## 许可证与来源

本项目采用 Apache License 2.0。继承代码的版权和来源说明保留在根目录及 Skill 目录内的 `LICENSE` 与 `NOTICE` 文件中。
