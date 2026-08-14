# Content to Editable PPT Skill 非功能需求与质量指标 v1.5

## 文档地位

本文档是 [v1.4](../v1.4/non-functional-requirements.md) 的增量权威版本。既有 Windows、PowerPoint COM、离线 Tabler、安全 Hash 和不可变 Artifact 要求继续有效。

## 一致性与确定性

- 同一结构化输入必须生成逐字节一致的页面 Prompt；
- Prompt Package、Style Anchor、Design Preview、Reconstruction Spec 和提取资产必须有 Canonical Hash；
- 已解析 SVG 在 Preview 与 Builder 调用前的 Source Hash 必须一致；
- Prompt 固定不被视为像素可复现保证，跨页一致性还必须由 Style Anchor 和 Deck Consistency Review 验证；
- 页面顺序变化不得无条件失效全部页面，只有相关 Authority 输入变化才重建。

## 性能与恢复

不设置固定总时长 SLA。必须记录每阶段耗时、调用类型、模型版本、重试和复用结果，并满足：

```text
Prompt Compilation Agent Calls = 0
Automatic Design Regeneration = 0
Automatic Full-deck Redesign = 0
Technical Retry <= 2 per stage
```

实现必须支持页面级缓存、Hash 驱动失效、断点恢复、有限并行和幂等发布。确定性 Blocking 必须阻止后续生图、Planner 或 Reviewer 调用。

## 安全与质量

- Design Preview 提取不得包含正式文字、隐私信息或无关相邻对象；
- 禁止整页位图替代可编辑重建；
- SVG、PNG/JPEG 和 PPTX 必须通过路径、外部关系和 Public-Safety 检查；
- Raster Handoff 失败不得伪装成成功资产；
- 正常交付必须满足 Content Drift = 0、Critical = 0、Major = 0；
- PowerPoint COM 技术失败只能进入 Technical Retry/Environment Failure，不得触发新语义规划。
