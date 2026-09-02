# Content to Editable PPT Skill

将用户提供的材料转为可编辑 PowerPoint。多页主路径只要求用户提供材料、确认一次页面方案，然后交付 PPTX 与预览；单张参考图片重建继续由独立兼容入口支持。

## 使用方式

### 多页 Content-to-Deck

宿主先阅读主题、文档或大纲，展示一份合并页面方案（页面顺序、标题、关键信息、视觉方向和所需图片），并等待用户确认。确认后由宿主生成 `deck-build-request.json`，使用唯一多页入口：

```powershell
python .\\content-to-editable-ppt\\scripts\\run.py `
  --request <deck-build-request.json> `
  --work-dir <new-work-directory> `
  --output-dir <new-output-directory> `
  [--asset-root <asset-directory>] `
  [--node <node.exe>]
```

`work-dir` 与 `output-dir` 必须尚不存在，且三类目录不能互相包含。若使用图片或 SVG，必须提供 `asset-root`；请求中的资产路径相对于该目录，且 SHA-256 必须匹配。

成功时 `output-dir` 恰好包含：

- `<output_name>_editable.pptx`
- `<output_name>_preview.png`

新多页入口会在发布前进行 Microsoft PowerPoint 环境检查、构建、渲染、往返保存、结构 QA 和预览生成。任一步失败不会产生 `output-dir`；诊断保留在 `work-dir`。

### 单张参考图重建

`content-to-editable-ppt/scripts/run_pipeline.py` 仍是独立、受支持的 Image-to-Editable-PPT 兼容入口。它完整保留既有 Planner、Visual Reviewer、Recovery、Review Gate、Warning Acceptance、Delivery Decision 与七文件交付流程。它不用于多页 Content-to-Deck。

## 多页请求边界

`deck-build-request.json` 固定声明确认状态、幻灯片顺序、精确英寸坐标、原生 Text/Shape/Line/Image/Chart 元素和本地资产。文字必须是原生对象并携带 `content_ref`；图片不得覆盖文字或整页替代内容。入口不接受旧状态、历史 Manifest、测试 Fixture、Evidence 或 Replay 输入，也不提供用户级 `plan/build/verify/deliver` 子命令。

完整结构见 [Schema](content-to-editable-ppt/schemas/deck-build-request.schema.json)。

## 环境与验证

- Windows + Microsoft PowerPoint
- Python 3.10+，依赖见 [requirements.txt](content-to-editable-ppt/scripts/requirements.txt)
- Node.js 20+，依赖见 [package.json](content-to-editable-ppt/scripts/package.json)

```powershell
python .\\content-to-editable-ppt\\scripts\\verify_install.py --manifest .\\runtime-manifest.json
python .\\content-to-editable-ppt\\scripts\\run.py --help
```

## 当前权威

- [ADR-042 与 ADR-043](DECISIONS.md)：多页主入口与独立单页兼容边界。
- [SKILL.md](content-to-editable-ppt/SKILL.md)：依据 Accepted ADR 描述宿主和用户路径。
- [`run.py`](content-to-editable-ppt/scripts/run.py) 与 [`run_pipeline.py`](content-to-editable-ppt/scripts/run_pipeline.py)：当前两条 Runtime 实现与行为。
- [Skill 精简计划](docs/skill-simplification-plan.md)：阶段 1–3 的执行记录。

旧的多页阶段实现已在阶段 3 按依赖边界清理。旧 Architecture、Specification、Contract 和 Testing 文档仅保留为历史记录，不再是正式多页入口说明；单页 Runtime 的既有契约继续有效。

## 后续视觉优先重构研究

[视觉优先三阶段重构研究](docs/visual-first-redesign/README.md)基于当前代码、两条 Runtime 路径和 ADR-042/043，整理下一阶段可能采用的产品方向、Stage 1 目标设计以及 Stage 2 Benchmark。该目录属于研究与提案，不改变当前入口、Runtime 行为或 Accepted ADR。

Visual-first 代码改造目前已在 `codex/visual-first-code-refactor` 分支完成 P1～P3，下一阶段为 P4 Native Chart / Native Table / SVG 与 Builder、QA 能力补齐。分支实现尚未替代正式主路径；当前提交、验收证据和接力说明见 [实施状态](docs/visual-first-redesign/implementation-status.md)。

## 许可证与来源

本项目采用 Apache License 2.0。继承代码的版权和来源说明保留在根目录及 Skill 目录内的 `LICENSE` 与 `NOTICE` 文件中。
