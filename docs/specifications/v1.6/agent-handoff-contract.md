> 历史文档：本文件记录已废止的 P0～P5 多页契约，不能用于当前实现或用户流程。当前权威见根目录 README、`content-to-editable-ppt/SKILL.md`、ADR-042/043 与精简计划。

# Content to Editable PPT Skill Agent 职责与交接契约 v1.6

## 文档地位

本文档是 [v1.5](../v1.5/agent-handoff-contract.md) 的增量权威版本。本版新增 P5 阶段 Agent 职责边界。

## P5 职责分配

### Host（Orchestrator）

- 按顺序执行 manage_delivery.py 子命令；
- 只在确定性步骤通过后准备 Reviewer Evidence；
- 将 Exception Review 与 Deck Consistency Review 作为 fresh-context 独立调用；
- 记录用户 Minor Warning 接受消息及其 SHA-256；
- 不执行 Patch、Planner、重新生图或资产替换；
- 不修改 P4 Candidate 与任何 P4 产物。

### 确定性脚本

- 校验 P4 Authority Bundle 与哈希链；
- 执行 Final Integrity、Deck QA、Roundtrip、Contact Sheet 生成、Policy 计算、Decision 创建、Packaging 与 Verify；
- 所有 Reviewer Evidence 的组装与响应记录。

### Visual Reviewer（现有角色，复用）

- Exception Review：仅审查被绑定 QA issue 的异常页；
- Deck Consistency Review：一次 Logical Pass，只判断跨页/系统性一致性；
- **必须遵守冻结契约：The P5 Deck Consistency Review may identify cross-slide or systemic inconsistency, but MUST NOT reopen page-level P4 fidelity judgments that have already passed.**
- 不得修改任何 Artifact；不得计算最终 Delivery Policy。

## Reviewer 调用边界

- Exception Review：batch_size ≤ 4、batch_calls ≤ 2；每次调用必须绑定 QA issue_ids；
- Deck Consistency Review：每套 Deck 固定一次；
- 技术失败：initial + 2 retries 耗尽 → review_incomplete → P5 永远 Blocking；
- Unexpected Reviewer Calls（未绑定 QA issue 的调用）= 0 是 Gate 指标；
- 不允许 Planner 与 Reviewer 共享同一 Context ID（沿用既有规则）。

## Evidence 隔离

- prepare-* 子命令只产出 Evidence 包（Contact Sheets、报告 Hash、Issue 绑定）；
- record-* 子命令只记录响应与预算，不执行模型调用；
- Raw Layer、Prompt、Agent Raw Response 不进交付目录，但作为 Engineering Evidence 保留在运行目录。

## 上游恢复映射（Structured Upstream Revision）

```text
文字或数据                     → P1
Deck Visual System            → P3.2
Approved Preview / 视觉权威    → P3.3
页面重建、编辑性、几何          → P4
环境、安全、Roundtrip、包装     → P5 Failure/Retry
```

P5 阶段只记录 structured_upstream_revision，不执行任何上游阶段的修改。
