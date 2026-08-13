# Content to Editable PPT Skill 需求规格说明 v1.3

## 文档地位

本文档是 [需求规格说明 v1.2](../v1.2/requirements.md) 的增量权威版本。v1.2 中未被本文件修改的产品目标、Windows-only 范围和其他阶段需求继续有效。

## v1.3 变更摘要

- P2 Wireframe 正式产物改为 Host 生成的逐页 Markdown 文字线稿；
- 线稿必须体现每页真实内容和布局草稿；
- 默认在聊天中展示整套线稿，但不强制确认；
- SVG、PNG 和精确几何不再是 P2 产品要求；
- P2 重新打开，新 Gate 通过前不得进入 P3。

## P2 产品需求

P2 必须回答：

> 这一页呈现哪些已确认内容，这些内容在页面上如何分区、排列、分层并建立关系？

每页线稿必须包含：

- Slide ID、页序和标题；
- 完整的 Approved Slide Content；
- 由等宽字符组成的布局草稿；
- 布局和阅读顺序说明；
- 图片、图表、流程或示意图等视觉预留区（需要时）。

## 用户体验

- Host 默认逐页展示整套文字线稿；
- 用户可直接继续，不要求强制确认；
- 用户可指定某页修改布局，系统创建新 Wireframe Revision；
- 用户要求修改文字时返回 P1，不能在 P2 直接改变已确认内容；
- 用户明确跳过线稿查看时，系统仍生成并保存线稿，但不暂停。

## 非目标

P2 不负责：

- 生成 SVG、PNG 或其他 Wireframe 图片；
- 精确坐标、BBox、像素级尺寸和最终排版；
- 最终颜色、字体、图像、插画和艺术风格；
- PowerPoint 对象拆解、构建、渲染或视觉审核。

## 当前交付状态

SVG P2 是历史实现。Markdown Binder、Manifest、Validator、Revision 和 Gate 完成前，Skill 必须在 P1 完成后停止，不得宣称 P2 或完整 Content-to-PPT 已可用。
