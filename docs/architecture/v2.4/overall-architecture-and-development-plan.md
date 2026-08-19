# Content to Editable PPT Skill 总体架构与开发计划 v2.4

## 文档地位

本文档是 [v2.3](../v2.3/overall-architecture-and-development-plan.md) 的增量权威版本。v2.3 已完成的 P3.3 Approved Design Preview 与 P4 Constrained Reconstruction 保持有效；本版新增 P5 Final Integrity、Deck Review 与 Immutable Delivery。

## 当前状态

```text
P0 / P0.5 / P1 / P2             COMPLETE
P3.1 Tabler Core                COMPLETE
P3.1 Production Fallback        COMPLETE
P3.2 Visual System / Prompt     COMPLETE
P3.3 Design Preview             COMPLETE (D03 LIVE EVIDENCE)
P4 Reconstruction               COMPLETE (D03 LIVE RECONSTRUCTION)
P5 Deterministic Implementation COMPLETE (Authority / Roundtrip / Security / Package Candidate)
P5 Package Candidate            VERIFIED (delivery_forbidden = true)
P5 Live Deck Review             PENDING (ADR-040)
P5 Formal Delivery              NOT CREATED
P5 Formally Complete            false
v1 End-to-End                   false
Production-quality Release      Validated = false
Release / Tag                   NOT CREATED
```

P5 是验收与交付层，不重复 P4 的视觉重建验收，也不再修改 PowerPoint。

## 最终产品链路

```text
P1 Approved Slide Content
→ P2 Markdown Wireframe
→ P2.1 Visual Placeholder Intent
→ P3.1 Resolved Standard Assets
→ P3.2 Deck Visual System + Locked Prompt Package
→ Approved Style Anchor
→ P3.3 Approved Design Previews
→ P4 Visual Reconstruction Specs
→ Editable Per-slide PPT
→ P4 Candidate Deck + Post-Assembly Render Comparison
→ P5 Final Integrity Check
→ Deterministic Deck QA
→ PowerPoint Open/Save Roundtrip
→ Exception Review（仅异常页）
→ Deck Consistency Review（固定一次）
→ Delivery Policy
→ Immutable Decision
→ Runtime-locked Atomic Packaging
→ Delivered
```

## P5 边界

P5 验证并交付 P4 Candidate Deck：

- P5 Candidate PPTX SHA = P4 Candidate Deck SHA；
- P5 Renderer Identity / Version / Dimensions = P4 Post-Assembly Renderer Evidence；
- P5 Final Slide Decoded RGB Hash = P4 Post-Assembly Slide Decoded RGB Hash；
- 满足后 P4 Reconstruction Fidelity = inherited，P5 只保存继承关系与对应 P4 Report Hash；
- 任一不一致（candidate_hash_mismatch / render_runtime_mismatch / final_render_identity_mismatch）均在 Reviewer 调用前 Blocking；Renderer 环境变化返回 P4 Revalidation，不允许 P5 用新阈值重新解释 Approved Preview。

P5 不执行 Patch、Planner、重新生图或资产替换；P5 不修改 P4 Candidate；正式交付 PPTX 与 P4 Candidate 字节一致。

## P5 状态机

```text
p4_complete
→ p5_preflight
→ final_integrity_check
├─ mismatch → p4_revalidation_required
└─ pass
   → deterministic_deck_qa
   → roundtrip_check
   ├─ blocking → p5_failed
   └─ pass
      → exception_review_routing
      → deck_consistency_review_ready
      → live_review_pending
      → deck_consistency_review_complete
      → evaluating_delivery_policy
         ├─ upstream_revision_required
         ├─ awaiting_warning_acceptance
         └─ delivery_approved
      → packaging
      → delivered
```

## 两层 Hash 闭包

正式交付目录包含 7 个文件；Hash 闭包采用两层规则：

```text
P5 Gate Report / Deck Delivery State
├─ provenance_sha256（Provenance 自身 Hash 的唯一权威存放处）
│
└─ provenance.json
   ├─ <name>_editable.pptx sha256
   ├─ <name>_previews.zip sha256
   ├─ <name>_assets.zip sha256
   ├─ <name>_qa_report.json sha256
   ├─ <name>_deck_consistency_report.json sha256
   └─ <name>_delivery_decision.json sha256
```

Provenance 不包含自身 Hash（避免自引用循环）。Delivery Artifact Hash Closure = pass ⇔ Provenance 校验 6 个 sibling artifacts 且 P5 State/Gate 校验 Provenance artifact。

## Authority 分层（P5 新增）

```text
P4 Candidate Deck + P4 Authority Bundle（state / manifest / candidate-report / drift-report / render-report）
→ P5 Final Render Manifest（继承 P4 Fidelity）
→ Deck Final QA Report
→ Powerpoint Roundtrip Report
→ Exception Review Evidence（Issue-bound）
→ Deck Consistency Report（跨页/系统性判断）
→ Deck Delivery Decision（Immutable）
→ Packaging Runtime Lock（冻结）
→ 7 文件审计交付包（两层 Hash 闭包）
```

## Reviewer 职责边界

- Exception Review：仅异常页，batch_size ≤ 4、batch_calls ≤ 2；每次调用必须绑定 QA issue_ids；超过 8 个异常页 → systemic_visual_failure → 返回 P4；
- Deck Consistency Review：每套 Deck 固定一次 Logical Pass，只判断跨页/系统性一致性，MUST NOT reopen page-level P4 fidelity judgments that have already passed；
- review_incomplete 在 P5 永远 Blocking（ADR-040）；
- Unexpected Reviewer Calls = 0（未绑定 QA issue 的调用计数）。

## 确定性打包

- Packaging 使用 python.zipfile，参数冻结：compresslevel=9、entry_timestamp=1980-01-01T00:00:00Z、固定 entry_permissions、entry_order=lexical、filename_encoding=utf-8、固定 create_system / flag_bits / extra / comment / archive_comment / allowZip64 / directory_entry_policy；
- 相同输入 + 相同 Packaging Runtime Lock → ZIP 字节/SHA-256 必须一致；
- Packaging 是纯函数，只消费已冻结 Artifact，不产生新业务字段；
- 原子 Stage + Rename；已有目标仅在完整文件集合和 Hash 全部一致时视为幂等成功，否则拒绝覆盖。

## 最终标准

Candidate Hash Drift = 0；Final Render Identity Drift = 0；Content/Chart/Asset Drift = 0；Roundtrip Structural Drift = 0；Roundtrip Decoded Pixel Drift = 0；Critical = 0；Major = 0；Review Incomplete = 0；Unexpected Reviewer Calls = 0；Full-slide Raster Substitution = 0；Unsafe Relationships = 0；Delivered PPT Hash = P4 Candidate Hash；Package Hash Closure = pass；Packaging Runtime Lock = match；P0–P4 Regression = 0。

## 开发顺序

```text
P5 Final Integrity Contracts（文档 + Schema + 状态机 + Integrity/QA/Roundtrip）
→ Deck Consistency Review（Exception Batch + Deck Review + Structured Upstream Revision）
→ Delivery Package（Policy + Decision + Packaging Runtime Lock + 7 文件包）
→ P5 Final Gate（D03 Real Review、D05/D08 Replay、SKILL/README 启用）
→ Three-real-deck Field Validation（FUTURE / NON-BLOCKING）
```
