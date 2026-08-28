# Stage 2 研究、Benchmark 与决策

> **Status**：Research / Benchmark Pending（研究中，Benchmark 待执行）
> **Document type**：Technical Research + Decision Gate（技术研究与决策门禁）
> **Authority**：无当前 Runtime 决策权；只定义候选、假设、评测和最终选型门槛
> **Current runtime relationship**：不修改当前 [`run.py`](../../content-to-editable-ppt/scripts/run.py) 或 [`run_pipeline.py`](../../content-to-editable-ppt/scripts/run_pipeline.py)，不替换当前正式多页路线
> **Depends on**：[`01-product-requirements.md`](01-product-requirements.md)、[`02-stage1-design.md`](02-stage1-design.md)、[外部项目证据](references/external-project-and-source-review.md)
> **Next decision gate**：Benchmark Decision = `Passed`
> **Last updated**：2026-08-28

---

## 一、Stage 2 要解决什么

Stage 2 要回答：

> 在不改变 Stage 1 已确认正式内容的前提下，怎样把大纲和 Markdown 线框转换成专业、统一、多样，并适合 Stage 3 重建的 PPT 设计图？

当前文档同时承担三件事：

```text
研究候选
↓
定义 Benchmark
↓
记录最终 Decision
```

不再拆成两份研究文档。

当前 `run.py` 不调用 Visual Designer、Deck Visual System、Prompt Compiler、图片模型或 Deck Visual Reviewer；旧 Deck-only P3/P5 实现也已在精简阶段删除。以下内容均是未来候选，不是现有模块说明。

---

## 二、统一状态词

只使用：

- **Candidate**：已进入待测试列表；
- **Hypothesis**：推测可能有效，但尚无实验支持；
- **TBD**：尚未形成明确候选答案。

当前状态：

```text
Anchor Project: Future Slide — Candidate
Independent Visual Designer Agent — Hypothesis
Structured Deck Visual System — Candidate idea
Deterministic Prompt Compiler — Candidate idea
Primary Image Model — TBD
Fallback Image Model — TBD
Reviewer pass threshold — TBD
```

---

## 三、Stage 2 的质量目标

研究至少关注：

1. 第一眼专业感；
2. 构图质量；
3. 信息层级；
4. 页面类型与内容匹配；
5. 留白与视觉节奏；
6. 多页风格一致；
7. 页面构图多样；
8. 正式内容不被改写；
9. 避免“AI 卡片味”；
10. Stage 3 重建友好。

---

## 四、GitHub 选型原则

不采用：

```text
多个大型 Runtime 拼装
```

当前策略：

```text
One Anchor, Multiple References
一个主参考候选 + 多个辅助参考
```

原则：

- 最多只选一个未来 Anchor；
- 其他项目只提供质量规则、Prompt、Provider 或产品边界证据；
- Anchor Benchmark 不通过时优先换 Anchor，而不是继续拼项目。

---

## 五、Future Slide — Anchor Candidate

当前：

```text
bytonylee/future-slide — Candidate
```

主要关注：

```text
slide-design
gpt-image-slide-prompt
gpt-image-slide-render
```

其 Stage 1 页面规划与本项目已有 Stage 1 设计职责重叠，不作为优先移植对象。

### 当前 Hypothesis

Future Slide 式：

```text
整套视觉规律
↓
逐页结构化设计意图
↓
Prompt 编译
↓
整页设计图
```

可能比：

```text
简单直接 Prompt
↓
图片模型
```

带来：

- 更稳定的跨页风格；
- 更清晰的视觉层级；
- 更少随机卡片化；
- 更好的复杂页表现。

这必须由 Baseline 对照证明。

---

## 六、Deck Visual System — Candidate idea

当前研究保留：

```text
Deck Visual System
整套 PPT 视觉系统
```

可能描述：

- 视觉气质；
- 色彩关系；
- 字体层级关系；
- 留白与密度；
- 构图规律；
- 图表 / 表格语言；
- 插画 / 图片语言；
- 页眉 / 页脚规律；
- 反模式。

具体 Schema、文件名：**TBD**。

---

## 七、Observed / Inferred

如果用户提供参考 PPT / 图片：

```text
Observed
= 可以直接观察到的视觉规律

Inferred
= 基于有限参考做出的合理推断
```

目的：

- 不把推断伪装成用户明确要求；
- 不过度拟合单页样本；
- 让视觉决策可追溯。

当前为 Candidate 规则。

---

## 八、Slide Visual Design Spec — Candidate idea

当前 Hypothesis：

> Visual Designer 不直接自由写最终 Prompt，而先输出结构化单页视觉设计规格。

可能包括：

- 页面视觉目标；
- 主要视觉焦点；
- 内容区关系；
- 构图家族；
- 留白与内容密度；
- 视觉层级；
- 图片 / 插画需求；
- 图表 / 流程需求；
- 禁止项；
- Stage 3 重建注意事项。

具体字段：**TBD**。

---

## 九、Composition Families — Candidate idea

当前保留有限构图家族思路，例如：

```text
cover
statement
metric_hero
quote
flow
comparison
timeline
matrix
image_spread
split_visual
cards_grid
table
closing
```

最终枚举：**TBD**。

### 反卡片化

`cards_grid` 不应成为默认构图。

连续页面高度盒子化时，应在生图前或 Reviewer 阶段触发 Warning / Fail 候选。

---

## 十、Style Intake — Candidate idea

视觉方向优先级建议：

```text
1. 用户提供的参考 PPT / 样板页 / 图片
2. 用户明确的视觉要求
3. 根据内容提出专属视觉方向
4. 信息不足时再询问用户
```

避免：

```text
academic → 固定学术模板
business → 固定商务模板
education → 固定教育模板
```

PPT 类型是内容组织维度，不等于最终视觉模板。

---

## 十一、Prompt Compiler — Candidate idea

当前 Hypothesis：

```text
Slide Visual Design Spec
↓
Prompt Compiler
↓
Image Prompt
```

希望固定：

- Prompt 结构；
- Authority；
- 禁止项；
- Stage 3 重建要求；
- 字段顺序。

目标是降低不同页面自由 Prompt 造成的风格漂移。

---

## 十二、Image Generation Engine — TBD

图片模型与 Provider 尚未冻结。

未来比较：

- 图片专业度；
- 参考图能力；
- 跨页稳定性；
- 复杂信息表达；
- 文字区域可读性；
- 失败率；
- 速度；
- 成本；
- API 可控参数；
- Provider 可替换性。

不因为参考仓库使用某模型，就直接采用该模型。

---

## 十三、Visual Designer Agent — Hypothesis

当前研究倾向：

```text
Host
= 讲什么、怎么组织

Visual Designer
= 怎么设计才好看
```

但是否必须新增独立 Visual Designer Agent，仍需 Benchmark 证明。

---

## 十四、Representative Design Gate

Stage 2 Fail-fast 流程：

```text
视觉系统
↓
3 张代表页
↓
Representative Design Gate
↓
通过后再生成整套
```

代表页建议：

- 封面；
- 普通正文；
- 复杂信息页。

它：

- 只校准视觉方向；
- 不是正式 Approval；
- 不产生 `Approved Design Preview`；
- 不能直接进入 Stage 3。

---

## 十五、批量生成策略 — Hypothesis

代表页通过后：

```text
共享 Deck Visual System（Candidate）
+
共享视觉参考（Candidate；具体形式可能是 Style Anchor）
+
共享 Stage 1 Approved Content
↓
有限页面级并行
```

并发数：**TBD**。

这里的 `Style Anchor` 只是候选设计机制，不恢复旧 ADR-038/P3 的 Artifact、Schema 或 State 合同。

目标：

- 保持一致性；
- 减少等待时间；
- 失败页局部重生成；
- 避免整套返工。

---

## 十六、Visual Reviewer — Candidate role

Reviewer 研究应覆盖：

### 单页

- 专业感；
- 构图；
- 层级；
- 留白；
- 视觉焦点；
- 页面类型匹配；
- 是否卡片化。

### 整套

- 跨页一致；
- 构图多样；
- 后半段漂移；
- 图表 / 流程 / 图片页是否保持同一视觉语言。

### Stage 3 兼容

- 正式文字区域是否清楚；
- 复杂视觉是否可独立提取；
- 主视觉边界是否清楚；
- 是否存在过度缠绕和难重建光效。

实现方式和阈值：**TBD**。

---

## 十七、辅助参考项目

### SlideSpeak

定位：

```text
Quality Engineering Reference
```

参考：

- Style Intake；
- 构图家族；
- 跨页多样性；
- Prompt 编译；
- 生图前质量 Gate。

不引入其完整 TypeScript / HTML Runtime。

### Design Image Studio

定位：

```text
Prompt / Image Engine Reference
```

参考：

- 结构化设计信息 → Prompt；
- Provider；
- 参考图；
- 重试；
- 成本；
- Fallback；
- 调用日志。

Benchmark 前不绑定其特定 Provider。

### Codex PPT

定位：

```text
Product Flow Reference
```

只参考：

```text
设计图
→ QA
→ 用户确认
→ Approved Design Preview
→ Editable Reconstruction
```

不作为已选 Runtime。

这里的 `Approved Design Preview` 仅表示未来经第二次正式确认的全套设计图，不指向已删除的旧 P3/P5 Runtime Artifact。

---

## 十八、明确不采用

当前不采用：

1. Future Slide + SlideSpeak + Design Image Studio + Codex PPT 的大型 Runtime 拼装；
2. Stage 2 重新规划 Stage 1 Storyline；
3. Stage 2 静默改写正式文字；
4. 所有页面默认卡片网格；
5. 未通过代表页 Gate 就批量生成；
6. Benchmark 前锁死图片模型；
7. Benchmark 前锁死 Anchor；
8. 代表页通过后直接标为 `Approved Design Preview`；
9. Benchmark 前编写 Stage 2 Runtime Implementation Plan。

---

## 十九、Benchmark 总原则

Benchmark 分两轮：

```text
Round A
验证设计流程是否真正比 Baseline 好

Round B
在已选流程下比较图片模型
```

不能把 Pipeline 价值和模型能力混在一起。

---

## 二十、Round A：Baseline vs Candidate Pipeline

固定同一个图片模型。

### Baseline

```text
简单直接 Prompt
→ 固定图片模型
```

### Candidate

```text
Structured Design System
+
Structured Page Prompt
→ 同一个图片模型
```

固定：

- Stage 1 内容；
- 页面；
- 图片模型；
- Provider；
- 尺寸；
- 参考图；
- API 所暴露的全部可控生成参数。

如果模型不暴露 seed / sampling 等参数，则通过稳定性测试评估不可控随机性。

---

## 二十一、Round A 的 Fail-fast 顺序

### A1：3 张代表页

只测：

- Cover；
- Body；
- Complex。

如果 Candidate 没有明显优于 Baseline：

```text
Round A = Failed
```

直接停止。

### A2：8～10 页连续 Deck

只有 A1 通过才执行。

检查：

- 跨页一致；
- 构图多样；
- 后半段漂移；
- 卡片化；
- 复杂页表现。

### A3：稳定性

只有 A2 通过才执行。

选 1～2 张关键页，各重复生成 3 次。

不重复完整 8～10 页 Deck 三次。

---

## 二十二、Round B：图片模型比较

### B1：3 模型 × 3 页

固定已经通过 Round A 的设计流程。

候选：

```text
Model A
Model B
Model C
```

具体型号：**TBD**。

淘汰明显较差模型。

### B2：Top 1～2 × 8～10 页 Deck

比较：

- 跨页一致性；
- 后半段漂移；
- 复杂页；
- 失败率；
- 耗时；
- 成本；
- Provider 可用性。

### B3：Top Model 稳定性

对最终候选模型选择 1～2 张关键页重复 3 次。

---

## 二十三、评分维度

建议总分 100：

| 项目 | 权重 |
|---|---:|
| 第一眼专业感 | 15 |
| 构图质量 | 15 |
| 信息层级 | 10 |
| 留白与视觉节奏 | 10 |
| 内容表达正确性 | 10 |
| 页面类型匹配度 | 10 |
| AI 模板感 / 卡片味控制 | 10 |
| 与视觉系统一致性 | 10 |
| Stage 3 重建友好性 | 10 |

分数不自动替代人工判断。

---

## 二十四、必须记录的失败类型

- 文字乱码；
- 错字；
- 伪文本；
- 改数字；
- 改专名；
- 编造图表；
- 主视觉过度抢占；
- 层级混乱；
- 页面过空；
- 页面过满；
- 卡片化严重；
- 连续构图重复；
- 风格漂移；
- 复杂流程画错；
- 重建边界不清；
- 生成失败；
- Provider / API 错误。

---

## 二十五、文字错误怎么判

### 可接受的生图文字瑕疵

如果：

- 文字区域位置正确；
- 层级正确；
- 行数和版面合理；
- 只是个别字形错误；

不应直接判整页视觉失败，因为 Stage 3 正式文字来自 Stage 1。

### 严重内容错误

如果模型：

- 改数字；
- 改专名；
- 新增不存在结论；
- 把正文变成随机标签；
- 使关键信息区域无法识别；

应视为严重问题。

---

## 二十六、Reviewer Agreement

主要定义为：

```text
Visual Reviewer 判定
vs
人工基准判定
```

建议从 Benchmark 图片中取约 10～20 张代表图，由人工先形成：

```text
Pass / Fail / Borderline
```

再比较 Reviewer 是否能识别：

- 卡片化；
- 风格漂移；
- 构图问题；
- 信息层级失败；
- Stage 3 重建风险。

Reviewer 模型与阈值：**TBD**。

---

## 二十七、成本记录

至少记录：

```text
Provider
Model
Page count
Generation calls
Successful calls
Failed calls
Regenerations
Average latency
Total latency
Estimated / actual cost
Reference-image usage
```

判断：

```text
质量提升
÷
额外成本
```

是否值得成为主路线。

---

## 二十八、Benchmark 结果

最终只允许：

```text
Passed
Failed
Inconclusive
```

### Passed

说明：

- Candidate Pipeline 相比 Baseline 有可解释改善；
- 连续 Deck 可保持视觉一致；
- 稳定性可接受；
- 至少一个模型满足质量 / 成本要求；
- Reviewer 与人工判断可用；
- Stage 3 重建友好性可接受。

### Failed

关键质量或稳定性不达标。

### Inconclusive

证据不足或实验条件不可靠。

---

## 二十九、新 ADR 门禁

只有：

```text
Benchmark Decision = Passed
```

才能进入：

```text
起草新 ADR
```

`Failed` / `Inconclusive`：

```text
继续研究
↓
不修改 Runtime
↓
不替换当前入口
```

---

## 三十、Decision Record

Benchmark 完成后直接填写本节：

```text
Benchmark Decision

Result:
TBD — Passed / Failed / Inconclusive

Anchor Candidate:
Future Slide — Candidate

Selected Pipeline:
TBD

Primary Image Model:
TBD

Fallback Image Model:
TBD

Evidence:
TBD

Known Limitations:
TBD

Reviewer Agreement:
TBD

Cost Summary:
TBD

Eligible for ADR Proposal:
No
```

只有 `Result: Passed` 时，最后一项才能改为：

```text
Eligible for ADR Proposal: Yes
```

---

## 三十一、当前状态

```text
Round A1 — Not run
Round A2 — Not run
Round A3 — Not run
Round B1 — Not run
Round B2 — Not run
Round B3 — Not run

Overall Decision — Inconclusive / Not evaluated
Eligible for ADR Proposal — No
```

---

## 三十二、Stage 2 通过后新增什么

如果最终：

```text
Benchmark Decision = Passed
```

再新增：

```text
04-stage2-design.md
```

只记录最终冻结内容：

- 是否使用独立 Visual Designer；
- Deck Visual System；
- Slide Visual Design Spec；
- Prompt Compiler；
- 主图片模型 / Fallback；
- Representative Design Gate；
- 批量生成策略；
- Visual Reviewer；
- 第二次正式确认；
- Stage 3 Handoff。

迁移和 `Main Mode / Fast Mode` 则由后续 ADR 决定，不再维护独立的 `target-architecture-and-migration.md`。
