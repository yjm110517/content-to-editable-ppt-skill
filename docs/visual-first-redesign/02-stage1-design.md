# Stage 1 目标设计：用户意图 → 大纲与 Markdown 线框

> **Status**：Target Design（设计已基本收敛，尚未实施）
> **Document type**：Stage Design（阶段目标设计）
> **Authority**：定义 Stage 1 未来目标行为；未实施前不能覆盖正式 `SKILL.md`
> **Current runtime relationship**：本轮不创建 Runtime Artifact、不创建 Schema、不修改现有 [`run.py`](../../content-to-editable-ppt/scripts/run.py) 或 [`run_pipeline.py`](../../content-to-editable-ppt/scripts/run_pipeline.py) 流程
> **Depends on**：[`01-product-requirements.md`](01-product-requirements.md)
> **Next decision gate**：Stage 2 Benchmark `Passed` → 新 ADR Accepted → Implementation Plan
> **Last updated**：2026-08-31

---

## 1. Stage 1 要解决什么

Stage 1 的核心任务：

> 把用户主题、文档、论文、已有大纲或其他材料，整理成逻辑完整、内容准确、来源可追踪，并能继续交给 Stage 2 的 PPT 规划结果。

目标链：

```text
用户意图 / 文件
↓
宿主代理（Host Agent）
↓
理解用户要求与材料
↓
Presentation Brief
↓
确定叙事策略与 Storyline
↓
生成整套大纲
↓
用户确认 / 修订大纲
↓
生成逐页正式内容
↓
Markdown Wireframe
↓
机器可读语义结构
↓
语义自检 / 确定性校验
↓
用户确认 Stage 1
```

---

## 2. Stage 1 由宿主代理统一完成

Stage 1 v1 固定由实际运行 Skill 的宿主代理连续完成，例如 Codex 或 Claude Code。Stage 1 不拆分独立的大纲规划代理、线稿规划代理或 Stage 1 审核代理。大纲规划与页面线稿规划是宿主代理在 Stage 1 内连续完成的任务阶段，而不是独立 Agent 调用。

宿主代理负责：

- 理解用户；
- 读取材料；
- 形成 Brief；
- 判断 PPT 类型；
- 规划 Storyline；
- 生成大纲；
- 生成正式内容；
- 生成 Markdown 线框；
- 形成机器可读的语义结构、元素关系和必要的结构化数据；
- 做一次语义自检；
- 与用户完成第一次正式确认。

v1 不新增：

```text
Outline Planner Agent
Wireframe Planner Agent
Stage 1 Reviewer Agent
```

### 2.1 为什么 Stage 1 不拆专业 Agent

Stage 1 的大纲、正式内容、页面结构和线稿具有强上下文连续性。用户在大纲确认过程中的修改会直接影响后续页面线稿，因此 v1 优先由宿主代理保持同一语义上下文连续完成。

v1 不为角色拆分本身增加额外 Agent 调用。只有未来真实 Benchmark 证明宿主代理在超长材料、超长 Deck 或上下文压力下持续出现质量问题时，才重新评估独立 Stage 1 Specialist。

---

## 3. Stage 1 的核心输出概念

```text
Presentation Brief
Structured Outline
Approved Content
Markdown Wireframe
机器可读语义结构
结构化数据
Validation Result
Approval
```

当前只定义概念和行为，不冻结 Runtime 文件名或 Schema。

为支持后续 Stage 2 与 Stage 3 的稳定 Handoff，宿主代理产生的已确认成果应至少保留 stable content IDs、region IDs 与 membership、confirmed relations / topology，以及出现 Chart / Table 时的结构化数据。Markdown / ASCII Wireframe 继续保留给人阅读；机器可读字段只服务跨阶段的确定性传递，不代表当前正式 Schema 已经新增。

这些概念尚未映射到当前 [`deck-build-request.schema.json`](../../content-to-editable-ppt/schemas/deck-build-request.schema.json)。当前多页宿主仍直接负责一次确认后的页面方案和精确坐标；未来 Stage 1 则有意停在内容与粗略线框边界，把最终视觉设计交给尚待验证的 Stage 2。

---

## 4. Presentation Brief

回答：

> 用户到底要一套什么 PPT？

建议包含：

```text
topic
audience
objective
presentation_type
target_slides
language
tone
must_include
constraints
source_ids
```

这些字段属于目标设计，不代表当前已经存在正式 Schema。

---

## 5. PPT 类型与叙事策略

v1 候选类型：

```text
education
academic
business_strategy
general
```

推荐叙事：

### 教育 / 教学型

```text
情境 / 问题
→ 概念
→ 原理 / 方法
→ 示例 / 活动
→ 应用
→ 总结 / 迁移
```

### 学术 / 研究型

```text
背景
→ 问题 / Gap
→ 研究问题
→ 方法
→ 结果
→ 解释
→ 启示 / 结论
```

### 商务 / 策略型

```text
现状
→ 核心问题
→ 证据
→ 方案 / 选择
→ 决策
→ 路线图 / 行动
```

### 通用说明型

```text
背景
→ 问题
→ 核心观点
→ 解释
→ 证据
→ 影响 / 启示
→ 结尾
```

用户明确指定结构时，用户要求优先。

---

## 6. Storyline

Stage 1 不能：

```text
长文档
→ 机械切成 N 页
```

而要回答：

- 这一页为什么存在；
- 上一页为什么通向下一页；
- 标题串起来能否讲清整套逻辑。

---

## 7. Structured Outline

每页目标上至少表达：

```text
slide_id
order
section
role
title
key_message
source_refs
visual_need
```

含义：

- `slide_id`：页面唯一编号；
- `order`：页面顺序；
- `section`：所属章节；
- `role`：页面为什么存在；
- `title`：页面正式标题；
- `key_message`：这一页最应该被记住的结论；
- `source_refs`：内容来源；
- `visual_need`：需要表达什么视觉关系。

---

## 8. 页面角色

当前候选：

```text
cover
orientation
context
problem
concept
explanation
evidence
comparison
process
synthesis
recommendation
closing
other
```

最终枚举未冻结。

---

## 9. Key Message

原则：

> 一页尽量只有一个核心 Key Message。

如果同一页承担多个彼此独立的主结论，应考虑拆页或重组。

---

## 10. Source References

用于：

- 追踪事实来源；
- 防止无依据扩写；
- 支持修改；
- 保护正式内容 Authority。

示例：

```text
manuscript:Methods.3.2
manuscript:Figure.2
user_requirement:R1
```

---

## 11. Visual Need

只回答：

> 这页需要表达什么视觉关系？

例如：

```text
type: process
semantic: 三周教学活动的递进关系
```

可以描述：

- 对比；
- 流程；
- 时间线；
- 关系；
- 证据；
- 表格；
- 图片 / 插画需求。

不能写：

- 精确坐标；
- HEX 色值；
- pt / px；
- 具体字体；
- 阴影；
- 渐变；
- 最终生图 Prompt。

这些属于 Stage 2。

---

## 12. Approved Content

Stage 1 决定：

- 标题；
- 正文；
- 数字；
- 专名；
- 表格数据；
- 引语；
- 核心结论。

第一次正式确认后，它们成为 Stage 2 的内容 Authority。

---

## 13. Markdown Wireframe

目标形式：

```text
Markdown
+
YAML Frontmatter
+
正式内容
+
Visual Need
+
ASCII Wireframe
```

示例：

```markdown
---
slide_id: S04
order: 4
section: 研究设计
role: process
title: 三周干预围绕知识连接逐步展开
key_message: GenAI 支持通过连接已有知识与 Python 新规则促进迁移
source_refs:
  - manuscript:Methods.3.2
visual_need:
  type: process
  semantic: 三周教学活动的递进关系
---

## 正式内容

- 第一周：激活已有程序结构知识
- 第二周：建立积木块与 Python 语法之间的对应关系
- 第三周：完成文本编程迁移

## 线框

┌─────────────────────────────────┐
│ 三周干预围绕知识连接逐步展开      │
│                                 │
│ [第一周] → [第二周] → [第三周]   │
│                                 │
│           [核心总结]             │
└─────────────────────────────────┘
```

---

## 14. 线框粒度

允许：

```text
左 / 右
上 / 下
中心
并列
递进
主视觉区域
文字区域
总结区域
```

禁止提前进入 Stage 2：

```text
x / y / width / height
HEX
pt / px
具体字体
阴影参数
渐变参数
图片生成 Prompt
```

---

## 15. 确定性校验

未来 Validator 可以检查：

### 结构

- Markdown / Frontmatter 是否可解析；
- `slide_id` 是否唯一；
- `order` 是否连续；
- 必填字段是否缺失。

### 来源

- `source_refs` 是否指向存在的来源。

### 阶段边界

发现明显 Stage 2 信息：

- 精确坐标；
- HEX；
- px / pt；
- 精确字体；
- 阴影 / 渐变。

### 内容容量

只先做 Warning，例如：

```text
content_overload_candidate
```

具体阈值未冻结。

---

## 16. 宿主代理语义自检

固定检查一次：

1. 叙事连贯性；
2. 标题序列；
3. 语义重复；
4. Key Message；
5. 来源相关性；
6. Visual Need 合理性。

不新增 Stage 1 Reviewer Agent。

---

## 17. 第一次正式确认

默认：

```text
Stage 1 候选
↓
确定性校验
↓
宿主代理语义自检
↓
用户审阅
↓
第一次正式确认
```

确认后冻结：

```text
Approved Presentation Brief
Approved Outline
Approved Content
Approved Markdown Wireframe
```

对于超长或高不确定任务，可以增加早期 Outline 预览作为 Fail-fast，但它不改变“两次正式确认”的产品定义。

---

## 18. Stage 1 成功条件

用户能够确认：

> 这套 PPT 就按这个逻辑讲；正式内容正确；每页大致结构没有问题；可以进入视觉设计。

---

## 19. 已收敛的 Stage 1 选择

当前已经收敛：

- 宿主代理负责 Stage 1；
- 不新增 Outline Agent；
- 有 Presentation Brief；
- PPT 类型与 Storyline 分离；
- 每页有 `role / key_message / source_refs / visual_need`；
- 正式内容与视觉设计分离；
- Markdown + Frontmatter + ASCII 线框；
- Stage 1 不输出精确坐标；
- 结构由确定性 Validator 检查；
- 语义由宿主代理做一次自检；
- 用户确认后形成内容 Authority。

---

## 20. 开放决策

以下暂不冻结：

- `role` 最终枚举；
- `visual_need` 最终枚举；
- 单页推荐最大文字量；
- Bullet 数量阈值；
- 表格最大行数；
- Runtime Artifact 实际文件名；
- JSON / Markdown 的最终持久化形式；
- 是否允许一次结构化输出自动 Repair；
- 超长 PPT 的具体阈值；
- Schema 最终字段。
