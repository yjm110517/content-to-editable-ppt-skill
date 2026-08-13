# Content to Editable PPT Skill 总体架构与开发计划 v2.1

## 1. 文档地位

本文档是 [v2.0 总体架构](../v2.0/overall-architecture-and-development-plan.md) 的增量权威版本。除本文件明确替换的 P2 Wireframe 定义、产物、流程、Gate 和阶段状态外，v2.0 的 Windows-only、Single-Slide Runtime、Agent 体系、P1、P3–P6 和 Release 要求继续有效。

本版本依据 [ADR-035](../../../DECISIONS.md) 将 P2 从 SVG 图形渲染子系统重定义为大模型生成的 Markdown 文字线稿。

## 2. 变更摘要

- `deck-wireframe.md` 成为唯一正式 Wireframe 内容本体；
- `wireframe-manifest.json` 只承担身份、Authority、Hash、页序、Revision 和状态绑定；
- SVG、PNG、精确坐标、BBox、Region Graph 和 Deterministic SVG Renderer 退出正式 P2；
- 旧 PR #12–#16、SVG 实现和 Gate 报告保留为历史工程证据；
- P2 重新打开，新的 Markdown Gate 通过前 P3 不 Ready；
- Sanitized SVG 继续作为 PowerPoint Runtime 的视觉素材格式。

## 3. 当前阶段状态

```text
P0 Baseline Freeze            COMPLETE
P0.5 Runtime Hardening        COMPLETE
P1 Host Content Planning      COMPLETE
P2 SVG Implementation         HISTORICAL
P2 Markdown Wireframe         REOPENED
P3 Visual Design              NOT READY
```

## 4. 正式 P2 架构

```text
P1 Approved Slide Content
          ↓
P1 Authority Validation
          ↓
Host Markdown Wireframe Pass
          ↓
Markdown Structure Validation
          ↓
Content Binding / Drift Validation
          ↓
Contract Correction ≤ 2
          ↓
deck-wireframe.md + wireframe-manifest.json
          ↓
默认在聊天中逐页展示
      ┌───────────────┴───────────────┐
      ↓                               ↓
用户要求布局修改                 继续 / 跳过查看
      ↓                               ↓
Wireframe Revision N+1             Accepted
      └───────────────┬───────────────┘
                      ↓
                 P2 Complete
                      ↓
                 P3 Visual Design
```

Image-to-Editable-PPT 继续绕过 P1、P2 和 P3，直接进入现有 Single-Slide Runtime。

## 5. 权威关系

```text
P1 Approved Slide Content
└─ 页面文字权威

P2 deck-wireframe.md
└─ 页面结构、布局草稿和信息关系权威

P3 Design Image
└─ 最终页面视觉权威
```

当三者发生冲突：

- 正式页面文字始终以 P1 为准；
- 页面结构与阅读顺序以已接受的 Markdown Wireframe 为准；
- 色彩、字体、图像、装饰和视觉细节以 P3 Design Image 为准；
- P2 的布局说明不得被解释为新增页面文字。

## 6. Markdown Wireframe 产物

目录：

```text
wireframes/
├─ deck-wireframe.md
└─ wireframe-manifest.json
```

`deck-wireframe.md` 每页按固定顺序包含：

1. Slide ID、页序和标题；
2. `页面内容`：完整列出 P1 已确认标题和全部 Content Blocks；
3. `布局线稿`：用等宽字符、框线、箭头和空间关系表现页面布局草稿；
4. `布局说明`：说明信息层级、相对位置、视觉预留区和阅读顺序。

页面内容必须完整。布局线稿可以用真实标题、短句或 Content Block 标签表示长正文的位置，不承担最终文本排版。

## 7. Metadata Binder

Host 只生成干净的布局草稿。确定性 Binder 从 P1 Authority 写入完整页面内容和唯一合法 Metadata：

```html
<!-- p2:slide-id=S03 -->
<!-- p2:content-ref=S03-C01:start -->
权威文字
<!-- p2:content-ref=S03-C01:end -->
```

Binder 和 Validator 不接受其他注释变体。Host 不得直接构造、修改或猜测 Authority Metadata。

## 8. 极薄 Manifest

Manifest 只记录：

- Schema Version 和 Artifact Type；
- Deck ID 和 Wireframe Revision；
- Approved Outline 与 Slide Content Manifest Hash；
- Markdown 相对路径和 SHA-256；
- 每页 Slide ID、Order 和 Content Refs；
- `candidate | accepted | superseded` 状态。

Manifest 禁止记录：

- 坐标、BBox、页面尺寸或精确比例；
- Region、Parent、Overlap、Overlay、Z-Order 或 Layout Graph；
- SVG/PNG 路径或 Hash；
- 最终配色、字体、阴影、纹理和艺术风格。

## 9. Host 调用与修订

- Initial Host Wireframe Pass：1；
- Automatic Redesign：0；
- Contract Correction：最多 2 次，且必须绑定 Validator Issue；
- 用户布局修改：创建新的 Wireframe Revision，不计为自动 Correction；
- 用户文字修改：终止旧 P2，返回 P1 创建并确认新的内容 Revision。

Contract Correction 只能修复缺页、重复页、页序、Content Ref、必需章节和 Metadata Binding 等契约错误。两栏改三栏、页面角色变化或审美优化属于用户驱动 Revision，不得自动发生。

## 10. 展示策略

- 默认在聊天中展示整套逐页 Markdown 线稿；
- 不设置强制确认 Gate，用户说“继续”即可接受；
- 用户明确跳过查看时仍生成、验证并保存线稿，只是不暂停；
- 保存版包含 Metadata，聊天展示版隐藏内部注释和 Hash。

## 11. Legacy 隔离

正式 P2 Route 不得调用：

```text
manage_wireframe.py
validate_wireframe.py
render_wireframe.py
```

上述旧实现、旧 Schema、测试和报告暂时保留，等待 Markdown P2 Implementation 阶段决定迁移或删除。任何生产入口、Skill 指令或新 Gate 不得依赖它们。

该隔离不适用于 PowerPoint Runtime 的视觉素材链：SVG 图标或插画仍可经 `sanitize_svg.py` 和 `validate_assets.py` 处理后进入 PPT Builder。

## 12. 新 P2 Gate

新 Gate 至少证明：

- P1 Authority Hash 与实际输入一致；
- Slide 数、Order、Slide ID 和 Content Ref 完整；
- Approved Content 无遗漏、增加或改写；
- 每页具有页面内容、布局线稿和布局说明；
- Manifest 与 Markdown Hash 闭合；
- 默认展示、跳过查看、布局 Revision 和返回 P1 正确；
- 正式 P2 Route 不调用 SVG Renderer，也不生成 SVG；
- 旧 SVG 实现不能被 Production P2 Route 访问；
- P0、P0.5 和 P1 无回归。

新 Gate 通过后才能将 P2 标记为 COMPLETE，并开始 P3。
