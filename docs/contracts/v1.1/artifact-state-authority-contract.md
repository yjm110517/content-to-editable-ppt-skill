# Content to Editable PPT Skill Artifact、State 与权威数据契约 v1.1

## 文档地位

本文档是 [Artifact、State 与权威数据契约 v1.0](../v1.0/artifact-state-authority-contract.md) 的增量权威版本。除本文件替换的 P2 Artifact、Authority、State 和失效规则外，v1.0 继续有效。

## P2 Authority 模型

| Artifact | 权威内容 | 生成者 | 下游权限 |
|---|---|---|---|
| Approved Slide Content | 页面正式文字 | P1 Deterministic Projection | 只读 |
| `deck-wireframe.md` | 页面结构、布局草稿、信息层级和关系 | Host + Deterministic Binder | P3 只读 |
| `wireframe-manifest.json` | Deck/页序/Content Ref/Revision/Hash/状态绑定 | Deterministic Runtime | 只读验证 |
| Design Image | 最终视觉表达 | P3 | Layout Planner 视觉遵循 |

P2 不产生第二份文字权威。Markdown 中的 `页面内容` 是 Approved Slide Content 的绑定副本；发生冲突时以 P1 为准，并将 P2 标记失败。

## 正式 Artifact

```text
wireframes/
├─ deck-wireframe.md
└─ wireframe-manifest.json
```

`deck-wireframe.md` 是唯一正式线稿本体。Manifest 不能代替 Markdown，也不能携带布局内容。

## Metadata Binding

合法格式只有：

```html
<!-- p2:slide-id=S03 -->
<!-- p2:content-ref=S03-C01:start -->
权威文字
<!-- p2:content-ref=S03-C01:end -->
```

Metadata 必须由确定性 Binder 注入。Host 输出、聊天展示和用户反馈不得直接修改它。

## Manifest 最小字段

Manifest 至少记录：

```json
{
  "schema_version": "1.0",
  "artifact_type": "markdown_wireframe_manifest",
  "deck_id": "D01",
  "revision": 2,
  "approved_outline_sha256": "...",
  "slide_content_manifest_sha256": "...",
  "wireframe_path": "deck-wireframe.md",
  "wireframe_sha256": "...",
  "slides": [
    {
      "slide_id": "S01",
      "order": 1,
      "content_refs": ["S01-TITLE", "S01-C01"]
    }
  ],
  "status": "accepted"
}
```

Manifest 不得包含 BBox、坐标、Region、Parent、Overlap、Overlay、Z-Order、SVG、PNG、Layout Graph 或最终视觉风格。

## Revision 与失效

- 用户布局修改创建新 Wireframe Revision，不覆盖旧 Markdown 或 Manifest；
- P1 Approved Content、Approved Outline 或 Projection Manifest 变化使当前全部 P2 Artifact 失效；
- 仅用户接受或跳过查看不改变 Markdown 内容 Hash；
- 用户文字修改进入 `p1_revision_required`，旧 P2 不可 Resume；
- P3 必须绑定 `status = accepted` 的当前 Manifest 和 Markdown Hash；
- Candidate、Accepted 和 Superseded 状态不得混用。

## Legacy Artifact

旧 Wireframe Spec、SVG、SVG Preview、几何 Validation Report 和旧 P2 State 属于 `legacy_p2_svg`，只用于历史审计和回归研究，不得进入新的 Production P2 或 P3 Authority Bundle。

PPT Runtime 中经安全清理的 SVG Asset 不属于 `legacy_p2_svg`，继续按照单页 Runtime 契约处理。
