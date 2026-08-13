# Content to Editable PPT Skill Agent 职责与交接契约 v1.4

## P2 Host

Host 只声明视觉语义、当前页 P1 Content Ref 来源和布局位置。Host 不得在 P2 写入 Tabler 名称、文件名、路径、SVG 或 Hash。

## P3 Host

Host 在当前 P3 Pass 中从非自动候选 Top-K 选择图标；不得增加独立图标 Agent 调用。Host 不得绕过 Resolver 指定任意外部文件，也不得让图像生成模型重绘已经解析的图标。

## Deterministic Runtime

Runtime 负责版本锁、索引、搜索、不可变 Resolution Record、Normalize、Sanitize、Asset Manifest 和双消费 Hash 验证。P3 Resolver 不解析 Markdown 业务字段。
