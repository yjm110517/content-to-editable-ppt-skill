# Tabler-first SVG 图标解析与程序化回退执行计划

## 状态

- Stage: P3.1 Asset Resolution
- Status: Accepted for implementation
- Primary library: Tabler Icons v3.46.0
- Pinned commit: `8ac7d81b72ece11072ef25ea9fd92e80c6f3c9fc`
- SVG rasterizer: `@resvg/resvg-js` 2.6.2

## 目标

将 P2.1 Visual Placeholder 解析为不可变 Resolution Record，再经过 Normalize、Sanitize 和 Validate 形成可供 Preview Compositor 与 PPT Runtime 共同消费的 Asset Manifest。

## 路由

```text
Existing Tabler
→ at most two-icon composition
→ constrained programmatic SVG
→ raster/image handoff
```

只有唯一 canonical name 或 official alias 自动采用；其他候选由当前 P3 Host Pass 从 Top-K 选择。程序化 SVG 禁止任意 Path，最多 12 个 Primitive、三层 Group、无文字和外部资源。

## Vendor

上游研究镜像使用 Cone-mode Sparse Checkout，仅选择 `icons/outline`。确定性同步脚本只复制 `LICENSE`、`aliases.json` 和 `icons/outline/**`，并生成提交到仓库的 Vendor Lock。

## 交付边界

P3.1 不生成正式 Design Preview。Gate 只用固定白底 synthetic fixture 证明同一 Sanitized SVG 能由 resvg/Pillow 和 PPT Runtime 输入链消费。
