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
- Composition Plan Source Input 与 PPT Builder Source Input 均绑定 Asset Manifest Sanitized SVG Hash；
- 不比较 SVG 与 PNG/OOXML Hash；synthetic resvg/Pillow fixture 分别记录 Sanitized SVG、Rendered Icon PNG 和 Preview Hash；
- P3.1 synthetic fixture 不含正式像素位置、颜色、Slot、Z-Order 或 Design Preview；
- 后续 Preview 与 PPT Runtime 必须物理消费已解析 SVG，Generative Icon Substitution 为 0；
- Tabler、resvg、Sanitizer、Asset Validator 与既有 P0–P2 无回归。
