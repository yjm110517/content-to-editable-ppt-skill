# P5 Final Integrity、Deck Review 与 Immutable Delivery 执行计划

## 状态

当前基线：

```text
main = b1554b1 + P5 deterministic hardening merged
P0–P4 = COMPLETE
P5 Deterministic Implementation = COMPLETE
P5 Package Candidate = VERIFIED (delivery_forbidden = true)
P5 Live Deck Review = PENDING (ADR-040)
P5 Formal Delivery = NOT CREATED
P5 Formally Complete = false
v1 End-to-End = false
Production-quality Release Validated = false
Release / Tag = NOT CREATED
```

## 冻结流程

```text
P4 Candidate Deck
→ Candidate / Render Identity Check
→ Deterministic Final Deck QA
→ Open/Save Roundtrip
→ Exception Review（仅异常页）
→ Deck Consistency Review（固定一次）
→ Delivery Policy
→ Immutable Decision
→ Runtime-locked Atomic Packaging
→ Delivered
```

核心不变量：Delivered PPTX SHA-256 = P4 Candidate PPTX SHA-256。

## 关键决策

- P5 继承 P4 Fidelity，不重新运行 Approved Preview Fidelity Comparator；只保存继承关系与 P4 Report Hash（ADR-041）；
- Renderer Identity / Version / Dimensions 必须等于 P4 Post-Assembly Renderer Evidence；环境变化 → p4_revalidation_required；
- Roundtrip 比较结构、语义与 decoded pixels，不比较 PPTX 字节；副本只作 Saveability Evidence；
- Exception Reviewer 调用是否发生不决定 Gate；只有未绑定调用（Unexpected Reviewer Calls）才失败；
- Deck Consistency Review 不可降级跳过（ADR-040）；review_incomplete 永远 Blocking；
- Deck Consistency Reviewer 不得重开已通过的 P4 页面级 Fidelity 判断；
- Minor Warning 必须用户明确接受；Clean Pass 不需要额外用户确认；
- P5 不修改 P4 Candidate；正式 PPTX 是主要交付物，其余 6 项为审计包；
- Provenance 记录 6 个 sibling 交付文件 Hash，自身 Hash 由 State/Gate 记录（两层闭包，避免自引用循环）；
- Packaging 是纯函数，在冻结 Packaging Runtime Lock 内字节确定；Fingerprint 不一致时停止。

## Gate

见测试计划 v1.4「P5 v1 Gate」与「P5 v1 Gate 最终标准」。报告落库：reports/p5/p5-final-deck-delivery-gate.json。

## PR 顺序

1. codex/p5-final-integrity-contracts（文档 v2.4/v1.6/v1.4 + ADR-040/041 + Schema + State/Integrity/QA/Roundtrip/CLI + 测试）
2. codex/p5-deck-consistency-review（Exception Batch + Deck Review + Structured Upstream Revision + 测试）
3. codex/p5-delivery-package（Policy + Decision + Packaging Runtime Lock + 7 文件包 + 两层 Hash 闭包 + 测试）
4. codex/p5-final-gate（D03 Real Review + D05/D08 Replay + Gate Report + SKILL/README 启用）

每 PR：latest main → deterministic tests → review → merge → post-merge verify → next。任一 Blocking 立即停止。
