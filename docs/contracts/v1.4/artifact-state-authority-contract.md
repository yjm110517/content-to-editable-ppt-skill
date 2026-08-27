> 历史文档：本文件记录已废止的 P0～P5 多页 Artifact 与状态契约，不能用于当前实现或用户流程。当前权威见根目录 README、`content-to-editable-ppt/SKILL.md`、ADR-042/043 与精简计划。

# Artifact、State 与权威数据契约 v1.4

## 文档地位

本文档是 [v1.3](../v1.3/artifact-state-authority-contract.md) 的增量权威版本。本版新增 P5 交付层 Artifact 的 Source of Truth、写权限与状态分离规则。

## P5 Artifact 清单与不可变性

| Artifact | 类型 | 不可变 |
|---|---|---|
| p5-final-render-manifest.json | Final Integrity | 是 |
| deck-final-qa-report.json | Deck QA | 是 |
| powerpoint-roundtrip-report.json | Roundtrip | 是 |
| exception-review-evidence.json | Reviewer Evidence | 是 |
| deck-consistency-report.json | Deck Review | 是 |
| warning-acceptance.json | Warning Acceptance | 是 |
| deck-delivery-decision.json | Delivery Decision | 是 |
| delivery-packaging-runtime-lock.json | Runtime Lock | 是 |
| delivery-provenance.json | Provenance | 是 |
| deck-delivery-state.json | **唯一可变状态** | 否（显式 transition） |

## Source of Truth

- P4 Candidate Deck（reconstruction-candidate.pptx）是 P5 唯一的 PPTX 输入与最终交付物来源；
- deck-delivery-state.json 是 P5 唯一可变状态，记录当前阶段、预算、计数器、已冻结 Artifact Hash 与 history（previous_sha256 链）；
- P4 Reconstruction Fidelity 的 Source of Truth 是 P4 Post-Assembly Renderer Evidence 与 Drift Report；P5 通过 Hash 绑定继承，不重新计算；
- Provenance 自身 Hash 的唯一权威存放处是 deck-delivery-state.current_artifacts.provenance_sha256 与 P5 Gate Report 的 provenance_sha256 字段。

## 写权限

- 确定性脚本可以创建/更新 deck-delivery-state.json 与各阶段 Report；
- 已冻结 Report（QA / Roundtrip / Review / Decision / Lock / Provenance）创建后不得覆盖；同内容幂等重写除外（Hash 一致）；
- Reviewer 不得修改任何 Artifact；
- manage_delivery.py 内部不调用模型；
- P5 不修改 P4 Candidate 与任何 P4 产物。

## 两层 Hash 闭包规则

```text
第 1 层：provenance.json 记录另外 6 个交付文件 SHA-256（不含自身）
第 2 层：deck-delivery-state.current_artifacts.provenance_sha256 与 P5 Gate Report 记录 provenance.json 自身 SHA-256
```

Provenance 不包含自身 Hash，避免自引用循环。Delivery Artifact Hash Closure = pass ⇔ 两层校验均通过。

## 状态机（P5）

```text
p4_complete → p5_preflight → final_integrity_check → deterministic_deck_qa → roundtrip_check
→ exception_review_routing → deck_consistency_review_ready → live_review_pending → deck_consistency_review_complete → evaluating_delivery_policy
→ packaging → delivered
分支：p4_revalidation_required / p5_failed / upstream_revision_required / awaiting_warning_acceptance / delivery_approved
```

任一状态转换必须：合法、记录 previous_sha256、绑定相关 Artifact Hash。

## Canonical 序列化

所有 P5 正式 JSON Artifact 使用 Canonical 序列化（RFC 8785 / JCS + Unicode NFC + UTF-8 + LF + No BOM），沿用 canonical_artifact.py。Packaging 是纯函数：只消费已冻结 Artifact，不产生新业务字段（禁止时间戳、随机 UUID、临时目录、用户名、绝对路径）。
