# Content to Editable PPT Skill 功能规格说明 v1.6

## 文档地位

本文档是 [v1.5](../v1.5/functional-specification.md) 的增量权威版本。本版新增 P5 验收与交付功能规格。

## P5 公共入口

`manage_delivery.py` 提供 14 个子命令：

```text
init                       校验 P4 Authority 并创建 deck-delivery-state（p4_complete → p5_preflight）
verify-final-integrity     Candidate SHA / Renderer Identity / 重渲染 + Decoded RGB Hash
run-deck-qa                Deck Final QA → deck-final-qa-report.json
run-roundtrip              临时副本 Open/SaveAs/Reopen/Render → powerpoint-roundtrip-report.json
prepare-exception-review   组装异常页 Reviewer Evidence（绑定 QA issue_ids）
record-exception-review    记录 Exception Review 响应与预算
prepare-deck-review        组装 Deck Consistency Review Evidence（Contact Sheets 等）
record-deck-review         记录 Deck Consistency Review 响应与 Structured Upstream Revision
evaluate                   确定性计算评审结果与 Delivery Policy 状态
record-warning-response    记录用户 Minor Warning 接受（绑定消息 SHA-256）
create-decision            产出不可变 deck-delivery-decision
lock-packaging-runtime     采集并冻结 Packaging Runtime Lock
package                    原子产出 7 文件审计交付包
verify                     反验证交付目录 Hash 闭包与 Delivered PPT Hash
```

CLI 只准备或消费 Reviewer Evidence，不在内部调用模型。每个子命令验证当前 State 并执行合法状态转换，历史记录保存 previous_sha256。

## P5 状态机

```text
p4_complete → p5_preflight → final_integrity_check → deterministic_deck_qa → roundtrip_check
→ exception_review_routing → deck_consistency_review_ready → live_review_pending → deck_consistency_review_complete → evaluating_delivery_policy
→ packaging → delivered
分支：p4_revalidation_required（integrity mismatch）/ p5_failed（blocking）/ upstream_revision_required / awaiting_warning_acceptance / delivery_approved
```

## Final Integrity 功能

1. 输入 P5 Candidate PPTX 的 SHA-256 必须等于 P4 candidate-deck-report 的 candidate_pptx_sha256；
2. Renderer、renderer_version、宽高必须等于 P4 candidate-render-report；
3. 重渲染 Candidate（新输出目录，不覆盖 P4 产物），按页计算 decoded RGB hash 并与 P4 Post-Assembly 渲染比较；
4. decoded_rgb_sha256 定义：sha256(Image.open(png).convert("RGB").tobytes())；
5. 输出 p5-final-render-manifest.json，记录 P4 报告 Hash 与 p4_fidelity_inherited = true；
6. mismatch codes：candidate_hash_mismatch / render_runtime_mismatch / final_render_identity_mismatch，均在任何 Reviewer 调用前 Blocking。

## Deck Final QA 功能

验证项分组：

- Slide 数量、顺序、尺寸和 ID；
- P1 正式文字与 Chart 数据（经 P4 Authority Bundle 回溯）；
- Native Text、Shape、Chart、SVG/Raster 对象计数；
- 字体、Fallback、Overflow；
- 空白页、丢失对象、整页位图替代；
- 宏、OLE、外部关系、链接媒体和活动内容；
- P4 State、Manifest、Candidate、Assembly Report Hash 链；
- Content / Asset / Chart Drift = 0。

输出 deck-final-qa-report.json，issues 绑定 slide_ids，并标记 exception_pages。

## Roundtrip 功能

- 使用 P4 Candidate 的临时副本：Open → SaveAs 临时副本 → Reopen → Render All Slides；
- 比较：Slide 数量/顺序/尺寸、Canonical Text、期望元素计数、Chart 数据、Asset 关系安全、外部关系 = 0、宏/OLE = 0、Decoded RGB Slide Hash 相等；
- 不比较 Roundtrip PPTX SHA 与原始 PPTX SHA；
- 输出 powerpoint-roundtrip-report.json；副本只作 Saveability Evidence，绝不进入交付。

## Reviewer 集成功能

### Exception Review

- 输入：异常页（存在绑定 QA issue 的 slide）；
- 批量：batch_size ≤ 4、batch_calls ≤ 2；超过 8 个异常页 → systemic_visual_failure → 返回 P4；
- 每次调用必须绑定 QA issue_ids；ledger 记录 role / call_id / live / bound_issue_ids；
- 复用现有 Visual Reviewer 与技术重试（initial + 2 retries）；
- D03 期望异常页为 0，但 Gate 不固定为 0；真正 Gate：Unexpected Reviewer Calls = 0 且 Issue-bound 调用 ≤ budget。

### Deck Consistency Review

- 每套 Deck 固定一次 Logical Pass；
- 输入证据：Approved Preview Contact Sheet、Final Candidate Contact Sheet、Approved-vs-Final Comparison Sheet、Deck Visual System 摘要、Final QA Report、Roundtrip Report、P4 Fidelity Inheritance Record、Exception Review Hash；
- 只判断跨页/系统性一致性：Typography、Palette、Background、Card/Border/Shadow 语言、Density/Spacing/Whitespace 与视觉节奏、Icon/Image/Chart/Diagram 处理、页眉页脚页码导航、Section Hierarchy、页面是否仍属于同一套 PPT；
- 不得重新开启已通过的 P4 页面级 Fidelity 判断；
- 输出 deck-consistency-report.json，含 Structured Upstream Revision。

### Structured Upstream Revision

```json
{
  "responsible_stage": "p4",
  "issue_ids": ["P5-I003"],
  "affected_slide_ids": ["S05", "S08"],
  "reason_code": "reconstruction_fidelity_major",
  "required_revision_scope": "local_pages"
}
```

阶段映射：文字或数据 → P1；Deck Visual System → P3.2；Approved Preview 或视觉权威 → P3.3；页面重建、编辑性、几何 → P4；环境、安全、Roundtrip、包装 → P5 Failure/Retry。P5 不执行 Patch、Planner、重新生图或资产替换。

## Delivery Policy 功能

```text
Critical / Major / Review Incomplete → 不可交付
Minor only → awaiting_warning_acceptance → 用户明确 accept → pass_with_warnings
No issues / Suggestions only → pass
```

- Warning Acceptance 绑定当前 QA、Review、Policy Hash 与用户消息 SHA-256；
- 决策输出 deck-delivery-decision.json，delivered_pptx_sha256 = P4 candidate sha256，显式覆盖 P4 报告的 delivery_forbidden: true；
- 决策一旦创建不可修改（Immutable Decision）。

## Packaging 功能

- 7 文件：<name>_editable.pptx（Primary，原字节复制 P4 Candidate）、<name>_previews.zip、<name>_assets.zip、<name>_qa_report.json、<name>_deck_consistency_report.json、<name>_delivery_decision.json、<name>_provenance.json；
- previews.zip：Final Contact Sheet + 逐页 Final Render + Manifest；
- assets.zip：仅 P4 实际消费的批准资产；
- provenance.json：P1–P4 Authority Hash、Final Integrity、Roundtrip、Reviewer（含 ledger 计数）、Decision、Runtime Lock、另外 6 个交付文件 Hash（不包含自身）；
- ZIP 构建参数冻结（见 Architecture v2.4「确定性打包」）；
- 原子 Stage + Rename；已有目标仅在完整文件集合与 Hash 全部一致时视为幂等成功，否则拒绝覆盖；
- Packaging Runtime Fingerprint 不一致 → packaging_runtime_mismatch → 停止；
- 排除清单：Raw Layer、Prompt、Agent Raw Response、临时 Roundtrip 文件、未接受 Revision。

## 7 文件 Hash 闭包（两层规则）

1. provenance.json 记录另外 6 个交付文件 SHA-256；
2. provenance.json 自身 SHA-256 由 package 完成后写入 deck-delivery-state.current_artifacts.provenance_sha256，并由 P5 Gate Report 的 provenance_sha256 字段记录；
3. Delivery Artifact Hash Closure = pass ⇔ 两层校验均通过。
