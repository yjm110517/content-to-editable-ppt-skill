# P1 Host Content Planning 阶段执行计划

## 1. 目标与边界

开发基线为 `main@707fd60`。P1 实现：

```text
Task Routing
→ Material Understanding
→ Candidate Outline + Exact Slide Content
→ User Revision / Confirmation
→ Approved Outline
→ Deterministic Projection
→ Approved Slide Content
→ Freeze
```

P1 不新增 Outline Planner Agent，不调用 Layout Planner 或 Visual Reviewer，不实现 Wireframe、视觉设计、多页 Runtime、Deck Assembly 或 Deck QA。用户确认后不得再由 Host 创作、改写或扩写页面文字。

权威依据：

- [总体架构 v2.0](../../architecture/v2.0/overall-architecture-and-development-plan.md)
- [测试与验收计划 v1.0](../../testing/v1.0/test-and-acceptance-plan.md)
- [Artifact、State 与权威数据契约](../../contracts/v1.0/artifact-state-authority-contract.md)
- [架构决策记录](../../../DECISIONS.md)

## 2. 调用预算

```text
Initial Host Planning Pass = 1
Automatic Host Regeneration = 0
Specialist Agent Calls = 0
```

Initial Pass 在同一上下文中生成 Material Understanding 和包含最终页面文字的 Candidate Outline。只有用户明确要求修改时才允许 Host Revision Pass；每次修改必须产生新 Candidate revision 并绑定用户请求哈希。Validator 失败不得触发自动 Host 重生。

## 3. 契约与哈希

P1 新增 Task Route、Deck Request、Material Understanding、Candidate/Approved Outline、Outline Confirmation、Approved Slide Content 和 Content Plan State 契约。现有单页 `request.schema.json` 保持不变。

所有权限边界哈希使用：

```text
canonicalization_version = p1-rfc8785-nfc-1
```

统一递归 NFC 后执行 RFC 8785 JCS 和 SHA-256。禁止浮点值、非有限数字、非字符串 Key、NFC Key 冲突和超出 JavaScript Safe Integer 范围的整数。Python helper 是唯一哈希权威，Node 不重复实现。

## 4. 路由与材料完整性

Task Route 为：

- `content_to_ppt`；
- `image_to_editable_ppt`；
- `needs_clarification`。

不明确的混合输入进入 `awaiting_route_clarification`，收到用户澄清后返回 routing。Image-to-PPT 直接 `p1_bypassed`，不得创建 Outline。

Required Material 只有在可靠读取或用户明确授权忽略后才能进入 `materials_ready`。Optional Unreadable Material 产生 Warning 但不阻塞。P1 不实现文件格式解析器，也不进行未经授权的外部研究。

## 5. Outline、确认和确定性投影

Candidate Outline 的标题和 Content Blocks 是最终页面文字；页面目的、核心观点和 Visual Intent 只是规划元数据。Confirmation 必须绑定 Candidate revision 和 Canonical SHA-256。修改后的 Candidate 必须重新确认。

Approved Slide Content 由 Approved Outline 确定性投影：保留 Slide ID、Order、Content Ref、Text 和 Source Ref，只允许 NFC 与换行标准化。任何缺失、重复、未知或变化的 Content Identity 都阻止 P1 Gate。

## 6. 测试与 Gate

冻结 D03、D05、D08 三套 Content Planning Fixture。D03 覆盖一次用户修改；D05 覆盖五页内容身份；D08 固定八页，覆盖顺序、来源、revision 和页面隔离。

最终要求：

```text
Blocking Issues = 0
Content Projection Drift = 0
Automatic Host Regeneration = 0
Specialist Agent Calls = 0
P0/P0.5 Regression = 0
```

P1 完成前不得进入 P2，不创建 Release 或 Tag。

## 7. PR 顺序

1. `codex/p1-1-contracts-canonical-hash`
2. `codex/p1-2-routing-materials`
3. `codex/p1-3-outline-confirmation`
4. `codex/p1-4-deterministic-content-freeze`
5. `codex/p1-5-content-planning-gate`
