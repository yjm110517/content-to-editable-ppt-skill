# Content to Editable PPT Skill 测试与验收计划 v1.1

## 文档地位

本文档是 [测试与验收计划 v1.0](../v1.0/test-and-acceptance-plan.md) 的增量权威版本。除 P2 Gate、受影响的 P3 输入和阶段状态外，v1.0 的 P0、P0.5、P1、P3–P6 与 Release 测试要求继续有效。

## 变更摘要

- 以 Markdown Wireframe Gate 替换 SVG Render Gate；
- 增加 Authority、完整性、结构、Metadata、Revision、聊天展示和 Legacy Isolation 测试；
- 新 P2 Gate 通过前 P3 测试不得启动；
- 旧 SVG P2 报告只作为历史证据。

## P2 测试夹具

继续使用 D03、D05、D08 的 P1 Authority Artifact：

- D03：3 页、默认聊天展示、一次用户布局 Revision；
- D05：5 页、长正文、图片/图表预留区、显式跳过查看；
- D08：8 页、页序、Content Ref 完整性和 Revision 隔离。

本 Gate 默认使用确定性 Host Fixture；Live Host Smoke 只在 Markdown Runtime 稳定后单独定义，不得成为日常回归前置条件。

## Markdown P2 Gate

### Authority

- P1 State 必须为 `p1_complete`；
- 实际 Approved Outline 和 Projection Manifest Hash 必须与 P1 State 一致；
- Markdown Manifest 必须绑定当前 P1 Authority；
- 修改任一 Authority Artifact 而沿用旧 Hash 必须失败。

### Completeness

- Slide 数、Order 和 Slide ID 与 Approved Outline 一致；
- 每页 Title 和所有 Content Ref 全部出现；
- 不允许漏页、重复页、跨页错配或未知 Content Ref。

### Content

- `页面内容` 与 Approved Slide Content Canonical Text 完全一致；
- 不允许摘要、扩写、改写、标点变化或新增页面文案；
- Layout Note 和占位标签不参与正式文字比较；
- Content Projection Drift 必须为 0。

### Structure

每页必须包含：

```text
Slide Identity
页面内容
布局线稿
布局说明
```

- 布局线稿必须引用本页真实标题、短句或 Content Block 标签；
- 长正文只要求在页面内容区完整，不要求塞入字符框；
- 缺少布局线稿或布局说明为 Blocking。

### Metadata 与 Manifest

- 只接受 `p2:slide-id` 和 `p2:content-ref=...:start/end` 固定格式；
- Metadata 必须与 P1 Content Ref 一一对应；
- Markdown SHA-256 与 Manifest 一致；
- Manifest 不得包含几何、SVG 或最终视觉字段；
- 篡改 Markdown、Manifest、Revision 或状态必须失败。

### Correction 与 Revision

- 每个 Pass 最多两次问题绑定的 Contract Correction；
- Correction 3 必须拒绝；
- 自动重设计次数必须为 0；
- 用户布局修改只创建新 Wireframe Revision；
- 用户文字修改返回 P1，旧 P2 不得 Resume；
- 历史 Revision 不被覆盖。

### Preview

- 默认生成并在聊天中展示全部页面；
- 聊天展示隐藏内部 Metadata 和 Hash；
- 显式跳过查看仍生成、验证并保存 Markdown，但不进入等待状态；
- 旧 Preview/Feedback 不得重放到新 Revision。

### No SVG 与 Legacy Isolation

正式 P2 Gate 必须证明：

```text
render_wireframe.py calls = 0
SVG outputs = 0
PNG wireframe outputs = 0
legacy P2 route calls = 0
```

静态和运行时检查必须确认 Production Skill Route 不引用旧 SVG P2 命令。与此同时，Single-Slide Runtime 的 Sanitized SVG Asset 测试必须继续通过。

## P2 通过标准

```text
Blocking Issues = 0
Authority Drift = 0
Content Drift = 0
Missing/Duplicate Content Refs = 0
Invalid Markdown Structure = 0
Unbounded Corrections = 0
Automatic Redesign = 0
Legacy SVG Route Calls = 0
Unexpected Revision Overwrite = 0
P0/P0.5/P1 Regression = 0
```

通过后才能将 P2 标记为 COMPLETE，并允许 P3 读取 Accepted Markdown Wireframe Bundle。

## 当前状态

在 Markdown Binder、Manifest Schema、Validator、Revision、聊天展示和本 Gate 尚未实现时：

```text
P2 Markdown Gate = pending
P3 = not ready
```
