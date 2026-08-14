# Content to Editable PPT Skill 功能规格说明 v1.5

## 文档地位

本文档增量替换 [v1.4](../v1.4/functional-specification.md) 的 P3.1 回退链，并新增 P3.2、P3.3、P4 和 P5 行为。未修改的 P0–P2 和单页 Runtime 要求继续有效。

## F05.2 标准资产解析与 Raster Handoff

P3.1 继续从 Accepted P2 1.1 Manifest 读取 `role=icon` Placeholder，并从固定 Tabler Outline 离线检索。唯一 canonical name、唯一 official alias 或 Host 从确定性 Top-K 中选择的准确图标可以物化为 Sanitized SVG。

没有准确匹配时生成 `Raster Handoff Pending`，不得自动进入组合图标或程序化 SVG。该状态保留 `visual_ref`、P2 Manifest Hash、语义和失败分类，等待 Approved Design Preview。

Design Preview 确认后，提取器只裁切目标小型视觉元素，并记录：

```text
approved_preview_sha256
visual_ref
crop_bbox
output_png_sha256
background_removal_status
extraction_quality
```

低分辨率、背景融合、遮挡、包含正式文字或无法安全分离时返回 `extraction_failure`。

## F06 Deck Visual System 与 Prompt Package

P3.2 输出未来 Artifact：

- `deck-visual-system.json`；
- `deck-prompt-package.json`；
- `style-anchor-record.json`。

Deck Visual System 冻结色板、字体层级、网格、间距、卡片/阴影语言、图片和图表处理、背景、页眉页脚及模板族。Prompt Package 冻结 shared prompt、negative prompt、模型、版本、比例和生成参数。

确定性 Prompt Compiler 使用以下输入生成每页 Prompt：

```text
Locked Deck Prompt
+ Slide Content
+ Markdown Wireframe
+ Visual Placeholder
+ Resolved Assets
+ Slide Role
```

Prompt Compiler 不调用模型。所有 Deck 先生成并确认一个主 Style Anchor；只有页面类别明显不同才允许有限辅助 Anchor。

## F07 Design Preview 与确认

P3.3 先生成不含正式文字权威的视觉主体，再由确定性 Compositor 注入 P1 正式文字、已解析 SVG 和可编辑图表预览。生成模型不得重绘已解析资产。

剩余页面在 Style Anchor 确认后按可配置批次生成。默认每页一次 Initial Generation，系统不得自动重生成。完成后以 Contact Sheet 集中展示，只有用户点名的 Slide ID 创建 Revision。

`design-preview-record.json` 必须绑定 Preview、Content、Prompt Package、Style Anchor、Asset Manifest 和用户确认消息 Hash。文字变化返回 P1；视觉变化创建新的 Design Preview Revision；旧确认不得复用。

## F08 Visual Reconstruction Spec

P4 为每个可见元素建立：

```text
element_id
content_ref / visual_ref
object_type
normalized_bbox
z_index
style_ref
asset_ref
editability_class
fidelity_priority
approved_preview_sha256
```

Layout Planner 只恢复几何、层级、构图和样式，不重新解释文字、事实、视觉语义或资产选择。全量 Deck 前先选一个复杂页执行 Reconstruction Smoke。

## F09 审核与交付

每页执行确定性内容、结构、编辑性和几何 QA。确定性证据标记异常时才调用页面 Visual Reviewer；整套 Deck 使用同一个 Visual Reviewer 执行一次 Contact Sheet 一致性审核，不新增 Deck Reviewer Agent。

最终比较 Approved Design Preview 与 PowerPoint Render。构图、主元素比例、层级、留白、视觉焦点和显著重叠属于 Critical/Major；阴影、渐变、纹理和微小渲染差异属于 Minor。Critical 或 Major 非零不得正常交付。
