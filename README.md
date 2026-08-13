# Content to Editable PPT Skill

`content-to-editable-ppt-skill` 的目标是把主题、文档或大纲转换为多页、可编辑的 PowerPoint 演示文稿。

## 当前状态

本仓库已完成 P0 Baseline Freeze、P0.5 Runtime Hardening 和 P1 Host Content Planning。原 SVG P2 已完成实现和集成，但 ADR-035 已将正式线稿重新定义为 Host 大模型生成的逐页 Markdown 文字线稿，因此 P2 已重新打开，P3 暂不 Ready。

当前可执行流程为“材料 → 待确认大纲 → 冻结页面文字”和“参考图片 → 可编辑单页 PPT”。新的“冻结页面文字 → Markdown 文字线稿”仍待实现。以下能力尚未实现，不能视为当前承诺：

- 最终页面视觉设计和设计图片生成；
- 从冻结页面内容自动生成完整多页 PPT；
- 跨页主题、字体和版式一致性；
- 图表、引用和来源管理；
- 面向完整演示文稿的多页视觉审核。

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
│  ├─ architecture/v2.0/、v2.1/
│  ├─ contracts/v1.0/、v1.1/
│  ├─ development/v1.4/
│  ├─ runtime/
│  │  ├─ v1.0/
│  │  └─ v1.1/
│  ├─ specifications/
│  │  ├─ v1.0/
│  │  ├─ v1.1/
│  │  ├─ v1.2/
│  │  └─ v1.3/
│  └─ testing/v1.0/、v1.1/
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

1. [总体架构与开发计划 v2.1](docs/architecture/v2.1/overall-architecture-and-development-plan.md) 决定当前阶段、模块边界、Markdown P2 和 Windows-only 范围。
2. [Architecture Decision Log](DECISIONS.md) 记录已经接受的关键决策、原因、后果和变更规则。
3. 对应产品、Runtime 和 Agent 专项规范定义实现要求。
4. [Artifact、State 与权威数据契约 v1.1](docs/contracts/v1.1/artifact-state-authority-contract.md) 定义 Source of Truth、写权限和状态分离。
5. [测试与验收计划 v1.1](docs/testing/v1.1/test-and-acceptance-plan.md) 定义新的 Markdown P2 Gate 及其余阶段验收标准。

### 当前产品规格（v1.3）

- [需求规格说明](docs/specifications/v1.3/requirements.md)
- [功能规格说明](docs/specifications/v1.3/functional-specification.md)
- [Agent 职责与交接契约](docs/specifications/v1.3/agent-handoff-contract.md)
- [非功能需求与质量指标](docs/specifications/v1.3/non-functional-requirements.md)

### Runtime 与实现规范

- [单页 Runtime 执行与错误恢复规范 v1.1](docs/runtime/v1.1/single-slide-runtime-and-error-recovery.md)
- [运行环境安装与引导规范 v1.1](docs/runtime/v1.1/environment-setup-and-bootstrap.md)
- [增量开发文档 v1.4](docs/development/v1.4/development-guide.md)

旧规格、架构 v2.0、Artifact 契约 v1.0、测试计划 v1.0 和 SVG P2 计划保留为历史基线。新开发和验收以 v1.3 产品规格、v1.1 Runtime 规范、v2.1 总体架构、Artifact 契约 v1.1 和测试计划 v1.1 为准。

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

当前 Markdown Binder、Manifest、Validator、Revision 和 Gate 尚未实现。Skill 在 P1 完成后必须停止并报告 `P2 Markdown realignment pending`，不得调用旧 SVG P2，也不得进入 P3。

[旧 P2 Gate 报告](reports/p2/p2-wireframe-gate.json) 与已合并 PR #12–#16 只作为 SVG 历史实现证据，不代表新的 Markdown P2 Gate 已通过。新的执行方向见 [P2 Markdown 重对齐计划](docs/plans/p2/text-wireframe-realignment-plan.md)。

## 下一阶段

新的 Markdown P2 Gate 通过后才进入 P3 Visual Design。在此之前，Content-to-PPT 可执行输出只到 Approved Slide Content，不能宣称已经完成文字线稿、完整多页 PowerPoint 生成或 P3 已就绪。

## 开发验证

Skill 基础结构可使用 Codex 的 `skill-creator` 校验器检查：

```powershell
python <resolved-skill-creator>\scripts\quick_validate.py .\content-to-editable-ppt
```

Node.js 运行时要求 Node.js 20 或更高版本。依赖声明位于 `content-to-editable-ppt/scripts/package.json`，Python 依赖声明位于 `content-to-editable-ppt/scripts/requirements.txt`。

## 许可证与来源

本项目采用 Apache License 2.0。继承代码的版权和来源说明保留在根目录及 Skill 目录内的 `LICENSE` 与 `NOTICE` 文件中。
