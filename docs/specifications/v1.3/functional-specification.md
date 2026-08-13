# Content to Editable PPT Skill 功能规格说明 v1.3

## 文档地位

本文档是 [功能规格说明 v1.2](../v1.2/functional-specification.md) 的增量权威版本，仅替换 F04 Wireframe 和受其影响的 P2→P3 交接。其他功能定义继续有效。

## F04 Markdown Wireframe

### 功能目标

Host 基于当前 P1 Authority Bundle，为每页生成可直接在聊天中阅读的 Markdown 文字线稿，同时表达完整页面内容和低保真布局草稿。

### 输入

- `p1_complete` State；
- Approved Outline；
- Projection Manifest；
- 全部 Approved Slide Content；
- Deck Request 中与布局有关的用户要求。

不得重新读取未确认 Candidate 或使用原始材料改写已确认内容。

### 输出

```text
wireframes/deck-wireframe.md
wireframes/wireframe-manifest.json
```

Markdown 是线稿内容本体；Manifest 只保存身份、Authority Hash、页序、Content Refs、Revision、Markdown Hash 和状态。

### 页面结构

每页固定包含：

```text
Slide Identity
页面内容
布局线稿
布局说明
```

`页面内容` 必须完整列出 P1 权威文字。`布局线稿` 使用真实标题、短句或内容块标签表达相对位置，不要求把长正文完整塞入字符框。`布局说明` 不属于页面正式文字。

### Authority Binding

确定性 Binder 写入：

```html
<!-- p2:slide-id=<slide-id> -->
<!-- p2:content-ref=<content-ref>:start -->
<approved text>
<!-- p2:content-ref=<content-ref>:end -->
```

Validator 必须拒绝缺失、重复、未知、乱序或非标准 Metadata，以及任何 Approved Content 漂移。

### 交互与状态

```text
candidate_ready
→ validating
→ ready_for_preview
├─ 默认展示 → continue / layout_changes_requested
└─ skip_view → accepted
```

- `continue`：接受当前 Revision；
- `layout_changes_requested`：创建新 Wireframe Revision；
- `content_changes_requested`：终止旧 P2 并返回 P1；
- 跳过查看不等于跳过生成和验证。

### Correction

每个 Initial 或 User Revision Pass 最多两次 Contract Correction。Correction 只能处理契约问题，不能自动更换布局模式或进行审美优化。

### 禁止行为

- 不调用 Layout Planner、Visual Reviewer 或图片生成；
- 不调用旧 SVG Wireframe Route；
- 不产生 SVG/PNG；
- 不修改 Approved Slide Content；
- 不进入 P3，除非新的 Markdown P2 Gate 已通过。

## F05 输入修订

P3 Visual Design 的正式输入改为：

```text
Approved Slide Content
+ Accepted deck-wireframe.md
+ wireframe-manifest.json
+ User Visual Requirements
+ Deck Visual Direction
```

P3 必须以 Approved Slide Content 作为文字权威，以 Markdown Wireframe 作为页面结构权威。
