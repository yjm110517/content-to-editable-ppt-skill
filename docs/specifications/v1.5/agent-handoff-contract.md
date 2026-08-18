# Content to Editable PPT Skill Agent 职责与交接契约 v1.5

## 文档地位

本文档增量替换 [v1.4](../v1.4/agent-handoff-contract.md) 的 P3 Host 行为，并收紧 Content-to-Deck 的 Planner 与 Reviewer 调用。既有两个 Specialist Agent 架构保持不变。

## Host

Host 负责一次 Deck Visual Direction、Style Anchor 编排、用户确认、Contact Sheet 展示和用户指定 Revision。Host 不得逐页自由重写 Deck 风格，不得自动重新生成页面，也不得增加 Visual Designer、Deck Reviewer 或 Icon Reviewer Agent。

Host 只能为准确的 Tabler 候选做当前 Pass 内选择。无准确匹配时必须保存 Raster Handoff Pending，不能调用组合或程序化 SVG 生产路由。

## Deterministic Runtime

Runtime 负责 Prompt 编译、Authority/Hash 验证、正式文字与已解析 SVG 合成、页面缓存、失效计算、Preview/Revision 状态、元素提取、PPT 构建和全部确定性 QA。

Prompt Compiler、Asset Resolver、Compositor、Extractor 和 Cache 均不得隐式调用模型。

## Layout Planner

P4 的初始 Visual Reconstruction Spec 由完整 Reconstruction Seed 确定性投影，Initial Planner Calls = 0。Seed 不完整时返回 P3.3，Layout Planner 不得根据 Preview 像素补齐实现方式。

Layout Planner 只在确定性 QA 产生可修复 Validation Issue 后生成局部 Targeted Patch。不得重新总结文字、替换资产、改变视觉语义、Reconstruction Class、P4 Strategy 或自由重新设计页面。

技术失败不得触发新的 Planner。局部问题优先 Targeted Patch，最多两轮视觉修订的既有上限继续有效。

## Visual Reviewer

独立 Image-to-Editable-PPT 继续保留逐页 Reviewer Gate。Content-to-Deck 改为：

```text
全部页面 Deterministic QA
→ 异常页面 Visual Reviewer
→ 一次 Deck Consistency Review
```

Deck Consistency Review 使用现有 Visual Reviewer 的新检查点，不创建新的 Agent。Reviewer 不修改 Spec，不因 Minor 或单次评分波动自动触发 Planner/生图调用。
