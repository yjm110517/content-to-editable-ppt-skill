# Content to Editable PPT Skill 非功能需求与质量指标 v1.3

## 文档地位

本文档是 [非功能需求与质量指标 v1.2](../v1.2/non-functional-requirements.md) 的增量权威版本。未变的 Runtime、Windows、PowerPoint、性能和质量要求继续有效。

## Markdown P2 质量要求

### 内容准确性

- 页面内容与 Approved Slide Content Canonical Text 必须完全一致；
- Content Ref 不得遗漏、重复、未知或跨页错配；
- 布局说明和占位标签不得被误判为新增页面文字；
- 内容漂移为 Blocking。

### 可读性

- 每页布局草稿必须能在普通 Markdown 等宽代码块中阅读；
- 不依赖颜色、图片、外部字体或 SVG；
- 长正文完整保存在页面内容区，布局线稿只表达结构，不承担最终排版；
- 聊天展示必须隐藏内部 Hash 和 Metadata 注释。

### 确定性与可恢复性

- Binder、Manifest Hash、Authority 验证和 Revision 状态必须确定性；
- 相同 Host 草稿和 P1 Authority 应产生相同绑定内容和 Hash；
- 非法输入不得部分覆盖已有 Revision；
- 历史 Revision 保留，不静默覆盖。

### 模型调用预算

- Initial Host Pass 为 1；
- Automatic Redesign 为 0；
- 每个 Pass 最多两次问题绑定的 Contract Correction；
- Validator 失败不得触发无界 Host 重生成。

### Legacy 隔离

- Production P2 Route 的 SVG Renderer 调用数必须为 0；
- Production P2 不生成 SVG 或 PNG；
- SVG P2 代码存在于仓库不得被解释为当前正式能力；
- PPT Runtime Sanitized SVG 资产支持必须保持不变。
