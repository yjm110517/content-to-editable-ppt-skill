# Content to Editable PPT Skill Artifact、State 与权威数据契约 v1.2

## Authority

| Artifact | Authority | Mutability |
|---|---|---|
| P1 Approved Slide Content | 页面文字 | Immutable |
| P2 Accepted Manifest 1.1 | 布局、Visual Placeholder Intent | Immutable revision |
| Icon Resolution Record | 选择的来源资产 | Write once |
| Asset Manifest Entry | Normalize/Sanitize/消费来源 Hash | Write once per materialization |
| Design Preview | 最终视觉预览 | P3.3 authority |

Resolution Record 只记录选择时已知的来源信息；后续 Hash 不得回写。Asset Manifest 必须绑定 Resolution Record SHA-256。

```text
Design Preview Source Asset Hash
= PPT Builder Input SVG Hash
= Asset Manifest sanitized_svg_sha256
```

不要求 Rasterized PNG Hash 或 PowerPoint 保存后的 OOXML 媒体 Hash 与输入 SVG Hash 相同。
