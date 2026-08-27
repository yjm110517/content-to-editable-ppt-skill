> 历史文档：本文件记录已废止的 P0～P5 多页测试与验收方案，不能用于当前实现或用户流程。当前权威见根目录 README、`content-to-editable-ppt/SKILL.md`、ADR-042/043 与精简计划。

# Content to Editable PPT Skill 测试与验收计划 v1.4

## 文档地位

本文档是 [v1.3](../v1.3/test-and-acceptance-plan.md) 的增量权威版本。本版新增 P5 v1 Gate 定义，并将三套真实 Deck Field Validation 移至 Release / Field Validation（非阻塞）。

## P5 v1 Gate

### D03（真实流程）

- 从已提交 P3.3 Evidence 通过 `--rebuild-p4-evidence` 重建真实 P4 三页 Candidate；不得依赖未跟踪的 `work/p4-final/D03`；
- Final Render Identity 继承 P4；
- Roundtrip Pass；
- Issue-routed Exception Calls 在预算内；
- 一次真实 Deck Consistency Review；
- Minor 存在时获取真实 Warning Acceptance；
- 正式 PPTX Hash 等于 P4 Candidate Hash；
- 7 文件交付包完整闭环（两层 Hash 闭包）。

### D05 / D08（确定性 Fixture + 冻结 Reviewer Replay）

- Review-run Agent Calls = 0（FixtureAdapter，live = 0）；
- D05 覆盖 Chart、SVG、Card、字体和资产；
- D08 覆盖 Connector、Order-sensitive Page、导航和恢复。

原“三套真实 Deck”要求移至 Release / Field Validation，不阻塞 P5 v1。

## P5 v1 Gate 最终标准

```text
Candidate Hash Drift = 0
Final Render Identity Drift = 0
Content / Chart / Asset Drift = 0
Roundtrip Structural Drift = 0
Roundtrip Decoded Pixel Drift = 0
Critical = 0
Major = 0
Review Incomplete = 0
Unexpected Reviewer Calls = 0
Full-slide Raster Substitution = 0
Unsafe Relationships = 0
Delivered PPT Hash = P4 Candidate Hash
Delivery Artifact Hash Closure = pass（两层规则）
Packaging Runtime Lock = match
P0–P4 Regression = 0
```

## 运行时测试清单（tests/runtime/）

- test_p5_final_integrity.py：candidate_hash_mismatch / render_runtime_mismatch / final_render_identity_mismatch 路径、继承关系、decoded RGB hash 正确性；
- test_p5_deck_qa.py：drift / unsafe relationship / 整页位图替代 / 异常页标记；
- test_p5_roundtrip.py：结构/语义/像素比较逻辑（真实 COM 仅 Gate D03）；
- test_p5_exception_review_routing.py：批量/预算/绑定、systemic 路径、Unexpected Calls；
- test_p5_deck_consistency_review.py：evidence 组装、upstream revision 映射、冻结 Replay、review_incomplete Blocking、禁止重开 P4 单页 Fidelity 契约；
- test_p5_delivery_policy.py：severity → policy 决策矩阵、warning acceptance 绑定；
- test_p5_packaging.py：字节确定性、runtime lock mismatch、幂等覆盖、两层 Hash 闭包、canonical 序列化与纯函数字段禁止；
- test_p5_gate.py：Gate 汇总指标断言。

## Field Validation（Release，非阻塞）

三套真实 Deck 类型：教育型、商务型、技术/流程型。通过标准另行在 Release 计划中定义；不阻塞 v1 Gate。
