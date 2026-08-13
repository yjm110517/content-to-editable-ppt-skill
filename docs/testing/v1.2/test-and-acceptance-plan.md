# Content to Editable PPT Skill 测试与验收计划 v1.2

## P2.1 Gate

- Visual Ref 在 Deck 内唯一且绑定当前页；
- Semantic Source Ref 非空、当前页有效且能支持 Semantic；
- Visual Ref 在布局草稿中恰好出现一次；
- P2 Artifact 不含图库、路径、SVG 或资产 Hash；
- P2 1.0 Artifact 不得直接进入 P3。

## P3.1 Gate

- Existing、Composition、Programmatic 和 Raster Handoff 路由正确；
- 正常解析无网络、无独立 Agent、无任意 SVG；
- Resolution Record 不覆盖；
- Composition Input 和 PPT Builder Input 均绑定 Asset Manifest Sanitized SVG Hash；
- synthetic resvg/Pillow fixture 记录独立 PNG 和 Preview Hash；
- Tabler、resvg、Sanitizer、Asset Validator 与既有 P0–P2 无回归。
