# Content to Editable PPT Skill 测试与验收计划 v1.3

## 文档地位

本文档是 [v1.2](../v1.2/test-and-acceptance-plan.md) 的增量权威版本。历史 P3.1 Gate 保留为工程证据；正式生产回退、P3.2、P3.3、P4 和 P5 以本版为准。

## P3.1 Production Fallback Cutover Gate

- 准确匹配的固定 Tabler 图标继续通过 Normalize/Sanitize/Validate；
- 无准确匹配返回 Raster Handoff Pending；
- 正式 Skill 路由不调用 Two-icon Composition 或 Programmatic SVG；
- 历史实现和报告保持可审计但不计入生产通过项；
- Raster Handoff Pending 不生成虚假 SVG、Asset Manifest Success 或 Consumption Contract；
- Preview 与 PPT Runtime 对标准 SVG 继续消费同一 Sanitized Source Hash。

## P3.2 Visual System 与 Prompt Gate

- Deck Visual Direction Host Pass = 1；
- Deck Visual System、Prompt Package、Negative Prompt、模型版本和参数完整绑定；
- Prompt Compiler 连续运行两次得到相同字节和 SHA-256；
- Prompt 编译 Agent Calls = 0；
- 所有页面 Prompt 继承同一 Deck 风格，且只注入允许的页面变量；
- 所有 Deck 在批量生成前拥有 Approved Style Anchor；
- Style Anchor 变化正确失效依赖页面。

## P3.3 Design Preview Gate

- 每页 Initial Design Generation 不超过 1；
- Automatic Design Regeneration 和 Full-deck Redesign 均为 0；
- 正式文字逐字来自 P1，并由确定性 Compositor 注入；
- 已解析 SVG 被物理合成，Generative Icon Substitution = 0；
- Contact Sheet、用户修改范围、Revision 和确认 Hash 防重放；
- 无匹配图标只能从当前 Approved Preview 提取；
- 提取 PNG 不包含正文、数字、标签、无关对象或整页内容；
- 低质量提取返回 `extraction_failure`。

## P4 Reconstruction Gate

- Reconstruction Spec 的每个元素绑定当前 Approved Preview；
- Content/Visual/Asset/Style Ref 全部闭合；
- 正式文字为原生文本，基础结构为原生 Shape，图表为可编辑结构；
- 标准图标使用已批准 Sanitized SVG；复杂视觉使用独立位图；
- Full-slide Raster Substitution = 0；
- 全量 Deck 前一个高风险页面 Reconstruction Smoke 通过；
- 页面缓存、Resume、局部失效和 Technical Retry 上限正确。

## P5 Final Gate

所有页面执行确定性 QA；只有异常页调用页面 Reviewer；整套 Deck 执行一次 Deck Consistency Review。最终必须满足：

```text
Content Drift = 0
Asset Drift = 0
Approved Preview Binding = pass
Critical = 0
Major = 0
Full-slide Raster Substitution = 0
Unsafe Relationships = 0
Prompt Compilation Agent Calls = 0
Automatic Design Regeneration = 0
Unexpected Agent Calls = 0
P0 / P0.5 / P1 / P2 Regression = 0
```

至少使用教育、商务和技术/流程三套真实多页 Deck 完整验证 Style Anchor、Design Preview、PPT 重建和 Deck 一致性。
