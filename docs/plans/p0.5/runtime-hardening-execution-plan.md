# P0.5 Runtime Hardening 阶段执行计划

本计划以 `main@d83a60e`、P0 Runtime `dbd8f15` 和冻结证据 `ce815cc` 为基线，增量加固单页 Runtime。P0.5 不进入多页内容规划，也不通过反复调用 Agent 追求视觉优化。

权威依据：[总体架构](../../architecture/v2.0/overall-architecture-and-development-plan.md)、[Runtime 规范](../../runtime/v1.1/single-slide-runtime-and-error-recovery.md)、[测试计划](../../testing/v1.0/test-and-acceptance-plan.md)、[Artifact 契约](../../contracts/v1.0/artifact-state-authority-contract.md)、[架构决策](../../../DECISIONS.md)和 [P0 报告](../../../baseline/baseline-report.md)。

## 执行原则

- Frozen Replay 是默认回归方式，Planner 和 Reviewer 调用数均为 0。
- M1–M4 不运行 B01–B06 全量 Live E2E；全量 Live E2E 只在 M5 执行一次。
- Live E2E 使用 Single-Pass Contract Mode：每个 Case 最多一次 Initial Planner 和一次 Initial Reviewer，不执行视觉 Revision。
- 确定性 Blocking 失败时立即停止测试批次，不继续调用 Agent。
- P0 Artifact 只读，兼容数据只生成到 `work/`。

## 测试分层与预算

| Tier | 内容 | Agent 调用 |
|---|---|---:|
| Focused | Unit、Schema、Fault Injection、受影响 Case Replay | 0 |
| Milestone | Frozen Replay B01–B06 | 0 |
| Live Smoke | 一个指定 Case、一个 Agent | 每阶段 1 |
| Final Gate | Frozen Replay 全量和 Single-Pass Live E2E | 12 |

预算为 M1=0、M2=1 个 Planner、M3=0、M4=1 个 Reviewer、M5=6 个 Planner加6 个 Reviewer。Live Agent 必须同时显式设置 `AllowLiveAgent` 和 `AgentCallBudget`；达到预算后立即失败。

## M1：测试基础设施与 Text Identity

P0 Authority 只有 `id/text`，Layout 只有元素级 `id/text`，没有 `content_ref/segment_order/joiner`，而且大多数 Authority ID 与 Layout ID 不一致。因此使用只读 Compatibility View：先匹配相同 ID 和相同 Canonical Text，再匹配唯一 Canonical Text；歧义、拆分或缺失必须由显式映射解决，禁止猜测。

B01 的 `footer` 在 P0 Layout 中缺失，As-Is Replay 应得到 `content_failure`。另设 P0.5 corrected fixture 验证后续 Build/Render，不能修改 P0。

建立 `live/fixture/failure/timeout_test` Agent Adapter、调用预算、Fail-Fast、故障注入和错误契约。

## M2：Preflight 与 Shared Validator

实现 Windows、Python/Node、PowerPoint、COM Smoke 和 Runtime Manifest。PR2 合并前在当前开发机真实执行一次 Preflight，但不破坏依赖、不测试真实 Repair、不调用 Agent。Shared Validation 分为 Core、Candidate、Post-Patch、Pre-Build 和 Final/Delivery Profile。

真实 Preflight 和 Frozen Replay 通过后，只对 B05 调用一次 Planner。Smoke 验收 Agent Transport、Schema、Validator 分类和 Runtime 路由，不要求 Planner 一次生成完美 Spec。

## M3：Recovery Engine

Targeted Patch、Technical Retry、Resume/Stage Reuse 分离。Technical Retry 每 Stage 最多两次，不调用 Planner。局部错误只有保存全局语义重分类证据后才允许一次 Limited Full Replan，总迭代仍不得超过三次。Patch、Retry、Resume 和 Zero-Asset 使用固定 Fixture 验证，不调用 Agent。

## M4：Reviewer 与内容权威

正常 Major/Critical 进入 `revision_required`；Reviewer 技术故障耗尽重试后，只有 Structural QA、内容和编辑性全部通过才允许 `delivered_with_warnings`。Canonical Text 使用 NFC、LF、`content_ref`、`segment_order` 和显式 `joiner`，只忽略布局软换行。

M4 只使用 B01 冻结 Source/Render 调用一次 Reviewer。Major 只要正确路由到 `revision_required` 即为 Smoke 通过，不得追加调用。

## M5：最终 Gate

先运行 Unit、Fault Injection、真实 Preflight 和 Frozen Replay。任何 Blocking 失败都禁止启动 Live E2E。确定性 Gate 通过后，按 B01 到 B06 顺序执行一次 Initial Planner、Runtime、Initial Reviewer，并停止，不进行 Revision。

单次新 Major/Critical 先标记 `agent_variance_candidate`。只有 Canonical Text、编辑性、拓扑、Structural QA 或 Frozen Replay 的确定性证据能够归因到 Runtime 时，才标记 `runtime_regression` 并阻止 P0.5。

Timeout Controller 使用每次休眠 6 秒、Controller 超时 5 秒的测试 Adapter，真实经过 Initial、Retry 1、Retry 2 和降级，不依赖外部服务。

## 接口与交付

- Layout 1.4 增加 `content_ref/segment_order/joiner`，并提供只读 1.3 Compatibility Loader。
- Run State 1.4 增加 Stage、计数器、哈希、复用结果和失败分类。
- 新增 Runtime Manifest、Runtime Error、Text Identity Map 和 Issue Attribution Schema。
- `run_pipeline.py` 保持现有必需参数兼容并增加由状态/哈希推导的 `--resume`。
- 依次交付五个 PR：Test Harness、Preflight/Validator、Recovery、Reviewer/Authority、Regression Gate。

P0.5 Gate 未全部通过时不得进入 P1，不创建 Release 或 Tag。Clean Windows 安装仍属于 v2.0 Release Gate。
