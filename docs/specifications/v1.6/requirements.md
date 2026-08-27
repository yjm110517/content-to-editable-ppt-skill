> 历史文档：本文件记录已废止的 P0～P5 多页需求，不能用于当前实现或用户流程。当前权威见根目录 README、`content-to-editable-ppt/SKILL.md`、ADR-042/043 与精简计划。

# Content to Editable PPT Skill 需求规格说明 v1.6

## 文档地位

本文档是 [v1.5](../v1.5/requirements.md) 的增量权威版本。v1.5 的 P3.3 Approved Design Preview 与 P4 Constrained Reconstruction 继续有效；本版新增 P5 Final Integrity、Deck Review 与 Immutable Delivery 需求。

## 产品目标

Skill 必须在完成 P4 可编辑重建后，证明交付物就是 P4 通过的那一份：保存不会坏、整套风格一致、文件安全、交付过程中没有被改动，并以不可变方式交付。

## P5 完整性需求

- 正式交付 PPTX 必须与 P4 Candidate Deck 字节一致（SHA-256 相等）；
- P5 Renderer Identity / Version / Dimensions 必须等于 P4 Post-Assembly Renderer Evidence；
- P5 Final Slide Decoded RGB Hash 必须等于 P4 Post-Assembly Slide Decoded RGB Hash；
- P4 Reconstruction Fidelity 通过继承关系保持有效，P5 不得重新解释 Approved Preview 阈值；
- 任一完整性不一致必须在任何 Reviewer 调用前 Blocking。

## Roundtrip 需求

- 对 P4 Candidate 的临时副本执行 PowerPoint Open → SaveAs → Reopen → Render All Slides；
- 比较 Slide 数量/顺序/尺寸、Canonical Text、元素计数、Chart 数据、关系安全、Decoded RGB Hash；
- 不要求 Roundtrip PPTX SHA 等于原始 PPTX SHA（PowerPoint 重写 OOXML 内部字节属正常现象）；
- Roundtrip 副本只作为 Saveability Evidence，绝不作为正式交付物。

## Deck 审核需求

- Deck Final QA 必须覆盖：Slide 数量/顺序/尺寸/ID、P1 正式文字与 Chart 数据、Native Text/Shape/Chart/SVG/Raster 对象、字体/Fallback/Overflow、空白页/丢失对象/整页位图替代、宏/OLE/外部关系/链接媒体/活动内容、P4 哈希链、Content/Asset/Chart Drift = 0；
- 异常页（存在绑定 QA issue 的页）进入 Exception Review：batch_size ≤ 4、batch_calls ≤ 2、每次调用必须绑定 issue_ids；超过 8 个异常页 → systemic_visual_failure → 返回 P4；
- 每套 Deck 必须完成一次 Deck Consistency Review（跨页/系统性一致性）；review_incomplete 永远 Blocking；
- Deck Consistency Review 不得重新开启已经通过的 P4 页面级 Fidelity 判断。

## 交付需求

- 策略：Critical/Major/Review Incomplete → 不可交付；仅 Minor → awaiting_warning_acceptance（用户明确接受后 pass_with_warnings）；无 issue 或仅 Suggestion → pass；
- Warning Acceptance 必须绑定当前 QA、Review、Policy Hash 与用户消息 SHA-256；
- 正式交付为 7 文件审计包（PPTX Primary + 6 项 Audit Bundle），Hash 闭包采用两层规则；
- 交付包在冻结的 Packaging Runtime Lock 内字节确定；Runtime Fingerprint 不一致时停止；
- 原子 Stage + Rename；已有目标仅在完整文件集合和 Hash 全部一致时视为幂等成功。

## 最终状态

P5 v1 Gate 通过只代表工程链路完成；Production-quality Release Validated = false；三套真实 Deck（教育/商务/技术流程型）Field Validation 属于 Release / Field Validation，不阻塞 v1。
