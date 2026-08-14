# Content to Editable PPT Skill 需求规格说明 v1.5

## 文档地位

本文档是 [v1.4](../v1.4/requirements.md) 的增量权威版本。v1.4 的 P2.1、固定 Tabler Core、离线解析和同源 SVG Hash 继续有效；本版替换正式资产回退，并新增视觉设计、设计确认、受约束重建和时间预算要求。

## 产品目标

Skill 必须先生成高质量图片版页面并取得用户确认，再将确认设计高保真重建为可编辑 PowerPoint。目标同时包括高视觉质量、确认后不漂移、感知结构保真和关键内容可编辑。

Approved Design Preview 必须成为视觉目标，P1 Approved Slide Content 必须继续作为文字权威。最终 PPT 不得通过整页截图伪装成可编辑页面。

## 正式资产要求

- P2 只声明视觉语义、P1 内容来源绑定和布局位置；
- P3.1 只为准确匹配的标准图标采用固定 Tabler SVG；
- 无准确匹配时必须进入 Raster Handoff Pending，待 Design Preview 确认后提取独立 PNG；
- Two-icon Composition 和 Programmatic SVG 不得进入正式生产路由；
- 已解析 SVG 必须被 Design Preview Compositor 和 PPT Runtime 物理消费，生成模型不得重绘；
- 提取 PNG 不得包含正式文字、无关元素或整页内容。

## 视觉设计要求

每套 Deck 必须冻结 Deck Visual System、Prompt Package、Negative Prompt、生成参数和 Approved Style Anchor。每页 Prompt 必须由确定性程序生成，不得由 Host 自由重写全局风格。

正式文字、数字、标签和已解析 SVG 必须由确定性 Compositor 注入 Design Preview。用户确认后的 Preview 必须绑定内容、资产、Prompt、Style Anchor 和用户确认消息 Hash。

## 重建和编辑性要求

Visual Reconstruction Spec 必须把 Preview 元素绑定到 `content_ref`/`visual_ref`、PPT 对象类型、BBox、Z-Order、Style、Asset、Editability Class 和 Fidelity Priority。

- 正式文字使用原生文本；
- 基础结构使用原生 Shape；
- 图表使用原生或可编辑结构；
- 标准图标使用 Sanitized SVG；
- 复杂视觉使用独立 PNG/JPEG；
- 禁止整页含正式内容位图。

最终 PPT Render 必须与 Approved Design Preview 对比，正常交付要求 Critical 和 Major 均为 0。

## 时间与调用要求

- Deck Visual Direction Host Pass 恰好为 1；
- Prompt 编译不得调用模型；
- 所有 Deck 必须先确认一个主 Style Anchor；
- 每页默认只允许一次 Initial Design Generation；
- 自动设计重生成和自动全 Deck 重设计均为 0；
- Technical Retry 每 Stage 最多 2 次且不得修改语义输入；
- 全页执行确定性 QA，页面 Reviewer 仅用于异常页；
- 每套 Deck 执行一次 Deck Consistency Review；
- 页面分批有限并行并支持 Hash 缓存、Resume 和页面级失效；
- 任一确定性 Blocking 失败必须在后续模型调用前停止。
