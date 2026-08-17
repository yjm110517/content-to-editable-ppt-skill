# P3 视觉设计与受约束重建执行计划

## 状态

本计划细化 [总体架构 v2.3](../../architecture/v2.3/overall-architecture-and-development-plan.md)、[功能规格 v1.5](../../specifications/v1.5/functional-specification.md)、[Authority 契约 v1.3](../../contracts/v1.3/artifact-state-authority-contract.md)和[测试计划 v1.3](../../testing/v1.3/test-and-acceptance-plan.md)。

```text
P3.1 Tabler Core                COMPLETE
P3.1 Production Fallback       COMPLETE
P3.2 Visual System / Prompt    COMPLETE (VISUAL QUALITY NOT EVALUATED)
P3.3 Design Preview            READY
P4 Reconstruction              BLOCKED BY P3.3 APPROVAL
P5 Deck Delivery               BLOCKED BY P4
```

## 实施顺序

### 1. Production Fallback Cutover

正式 Resolver 只保留准确 Tabler SVG 和 Raster Handoff Pending。组合/程序化 SVG 实现从 Skill 生产入口和新 Gate 隔离，历史测试和报告保留。

### 2. Deck Visual System 与 Prompt Compiler

实现 `deck-visual-system`、`deck-prompt-package` 和 `style-anchor-record` 契约。Host 只执行一次 Deck Visual Direction；确定性 Compiler 为每页注入 Approved Content、Wireframe、Visual Placeholder、Resolved Assets 和 Slide Role。

连续编译必须逐字节一致，且调用模型数为 0。生成调用前完成全部 Authority、Ref、Asset、路径和 Prompt 检查。

### 3. Style Anchor 与 Design Preview

先生成并确认一页代表性 Style Anchor，再以可配置 3–4 页批次生成其余页面。页面视觉主体由生图能力生成，正式文字、已解析 SVG 和可编辑图表预览由确定性 Compositor 注入。

完成后生成 Contact Sheet；系统只对用户指定 Slide ID 创建 Revision。每页默认一次 Initial Generation，自动重生成和自动全 Deck 重设计均为 0。

### 4. Preview Element Extraction

只处理 Raster Handoff Pending。输入必须是当前 Approved Design Preview；裁切目标小型视觉元素并尽量输出透明 PNG。包含正式文字、分辨率不足、背景严重融合、遮挡或无法分离时失败。

### 5. Constrained Reconstruction

建立 Visual Reconstruction Spec，将 Preview 元素映射为原生文本、Shape、Chart/Table、Sanitized SVG 或独立 PNG/JPEG。先选择最复杂页面完成 PowerPoint Reconstruction Smoke，再有限并行处理其余页面。

Layout Planner 只恢复几何、层级、构图和样式。技术失败使用原输入重试，局部视觉差异使用 Targeted Patch；不得重新解释内容或替换资产。

### 6. Deck Assembly 与最终 Gate

对所有页面执行确定性 QA，只把异常页交给 Visual Reviewer，并对 Contact Sheet 执行一次 Deck Consistency Review。最终 PowerPoint Render 与每页 Approved Design Preview 比较，Critical 和 Major 必须为 0。

## 性能策略

- Style Anchor 通过前不生成整套页面；
- 每阶段以 Canonical Hash 缓存和恢复；
- 单页变化只失效当前页；
- Contact Sheet 集中收集用户修改；
- 任一 Blocking 立即停止后续 Agent 或生图调用；
- 记录调用数、技术重试、复用结果和阶段耗时，不设置固定总时长 SLA。

## PR 顺序

1. Production Fallback Cutover；
2. P3.2 Contracts + Prompt Compiler；
3. Style Anchor + Preview Workflow；
4. Deterministic Compositor + Extraction；
5. P4 Reconstruction Spec + Runtime；
6. P5 Deck Assembly + Final Gate。

每个 PR 从最新 `main` 创建，完成确定性测试、审核、合并和 Post-Merge Verify 后再进入下一项。
