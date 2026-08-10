# Content to Editable PPT Skill Agent 职责与交接契约 v1.2


## v1.2 变更摘要

本版本不增加新的 Agent，继续冻结为 Host Agent、Layout Planner、Visual Reviewer 三个角色；仅同步总体架构 v2.0 的 Windows-only Runtime 术语和 Gate。

主要变化：

- Runtime 仍是确定性子系统，不新增 Runtime Agent；
- Host 必须在 Layout Planner 前确认 Windows、Microsoft PowerPoint 和 PowerPoint COM 全部 Ready；
- Runtime 未 Ready 时，Host 必须先调度 Bootstrap / Repair，无法恢复则产生 `environment_failure`；
- Layout Planner 与 Visual Reviewer 均不得承担 Python / Node / PowerPoint 环境安装与修复；
- Builder / Runtime 只使用 Microsoft PowerPoint COM 完成当前版本的渲染与 Office 自动化；
- Host、Planner 和 Reviewer 的其余权限边界保持不变。

---

## 1. 文档目的

本文档定义 `Content to Editable PPT Skill` 第一版中各 Agent / 角色的职责边界、输入输出、权限、禁止事项、权威信息源、上下文隔离要求以及角色之间的交接规则。

本文档用于解决以下问题：

- 谁负责什么；
- 谁不能做什么；
- 哪个角色拥有哪类修改权；
- 哪些信息可以作为权威来源；
- Agent 之间应传递哪些信息；
- 哪些上下文必须隔离；
- Reviewer 发现问题后由谁修复；
- 最终交付状态由谁决定。

第一版采用精简角色体系：

```text
Host Agent
├─ 内容理解与大纲规划
├─ 用户沟通与确认
├─ Wireframe 规划
├─ 视觉设计与生图调度
├─ 流程编排
└─ 最终交付判断

Layout Planner
└─ 图片到可编辑 PPT 的重建规划

Visual Reviewer
└─ 独立视觉审核
```

除以上角色外，PPT 构建、渲染、结构 QA、Deck 合并等确定性工作由 Runtime / Scripts 完成，不额外建立 Agent。

---

# 2. 设计原则

## 2.1 少 Agent 原则

只有满足以下条件之一时，才应建立独立 Agent：

1. 任务具有高度专业化的语义/视觉判断；
2. 独立性本身能够显著提升质量；
3. 与 Host 合并后会产生明显职责冲突。

第一版不设置：

- 独立 Outline Planner；
- 独立 Wireframe Planner；
- 独立 Visual Designer Agent；
- 独立 QA Agent；
- 独立 Revision Agent；
- 独立 Deck Reviewer。

对应能力由 Host Agent、Layout Planner、Visual Reviewer 与确定性 Runtime 分工完成。

## 2.2 功能阶段保留，Agent 数量精简

第一版仍保留完整功能阶段：

```text
内容理解
→ 大纲规划
→ 用户确认
→ Wireframe
→ 视觉设计
→ 页面设计图
→ 可编辑重建
→ 结构 QA
→ 独立视觉审核
→ 定向修订
→ Deck 整合
→ 交付
```

但不要求每个阶段都对应一个独立 Agent。

## 2.3 权威来源优先

任何下游 Agent 都必须遵循上游已确认的权威信息源。

禁止下游通过：

- OCR；
- 图片识别；
- 模型猜测；
- 自己的语言优化；

覆盖用户确认后的内容。

## 2.4 审核独立性

Visual Reviewer 必须使用独立上下文。

负责重建的 Layout Planner 不得替代 Reviewer 进行最终视觉审核。

## 2.5 确定性任务优先脚本执行

以下任务优先由脚本 / Runtime 完成：

- PPT 构建；
- 字体检查；
- PowerPoint 渲染；
- OOXML / 结构 QA；
- 资产检查；
- Deck 合并；
- 页面顺序检查；
- 基础交付 Gate。

---

# 3. 角色总览

| 角色 | 类型 | 主要职责 |
|---|---|---|
| Host Agent | 宿主 Agent | 总控、用户交互、内容规划、Wireframe、视觉设计调度、流程编排、交付判断 |
| Layout Planner | 专业 Agent | 将页面设计图规划为可编辑 PPT 对象和布局规格 |
| Visual Reviewer | 独立专业 Agent | 比较页面设计图与 PPT 实际渲染图，输出视觉审核结果和问题 |
| Runtime / Scripts | 确定性子系统（非 Agent） | Bootstrap、Preflight、Repair、Build、Render、QA、Deck 合并与验证 |

典型宿主环境：

- Claude Code；
- Codex；
- 其他后续兼容的 AI Coding Agent。

---

# 4. Host Agent 契约

## 4.1 角色定位

Host Agent 是整个 Skill 的总控角色。

它通常就是当前运行 Skill 的：

- Claude Code；
- Codex；
- 其他兼容宿主 Agent。

Host Agent 不是 Skill 内额外启动的专业子 Agent。

## 4.2 Host Agent 负责的功能

Host Agent 负责：

- 识别用户意图；
- 判断任务入口；
- 读取用户材料；
- 理解 PPT 要求；
- 生成候选大纲；
- 与用户讨论并修改大纲；
- 获取用户对大纲的最终确认；
- 规划 Wireframe；
- 决定是否展示 Wireframe；
- 规划视觉设计方向；
- 调用当前可用的图片生成能力；
- 生成或驱动生成页面设计图；
- 对需要 PPT 重建能力的任务发起 Runtime readiness 检查；
- Runtime 未 Ready 时调度 Bootstrap / Runtime Repair；
- 确认 Runtime Ready 后再调度 Layout Planner；
- 调度 Visual Reviewer；
- 根据 Reviewer 问题进行分类；
- 路由定向修订；
- 判断哪些页面允许并行；
- 调用确定性 Runtime；
- 根据固定 Delivery Gate 决定最终状态；
- 向用户交付最终成果。

## 4.3 Host Agent 可以做

Host Agent 可以：

- 根据用户材料总结、重组和生成候选大纲；
- 在大纲确认前根据用户反馈修改内容；
- 选择合适的 Wireframe；
- 根据用户要求决定设计风格；
- 在用户未规定部分进行视觉设计判断；
- 调用图片生成工具；
- 组织多页任务；
- 决定任务是否需要展示样张；
- 发起 Fast Preflight；
- 根据 Runtime 结果决定 Bootstrap、Repair 或 environment failure；
- 决定 Reviewer issue 应返回哪个阶段处理。

## 4.4 Host Agent 不可以做

Host Agent 不可以：

- 在大纲确认后擅自改写已确认内容；
- 绕过 Layout Planner 自己完成图片到 PPT 的正式重建规划；
- 绕过 Visual Reviewer 自己宣布视觉审核通过；
- 将 Reviewer 已确认的 Major / Critical 问题直接忽略；
- 为了提速取消结构 QA；
- 为了提速取消正式 Reviewer 调用；
- 把技术错误误判为内容规划错误并重新生成大纲；
- Runtime 未 Ready 时先调用 Layout Planner；
- 自行随机切换系统 Python / Node 环境绕过 Runtime 规范；
- 临时向用户全局环境随意 `pip install` / `npm install -g` 以规避受控 Runtime；
- 无上限重复调用 Planner / Reviewer。

## 4.5 Host Agent 的权威输入

Host Agent 应优先遵循：

1. 用户当前明确指令；
2. 用户已确认的大纲；
3. 用户视觉要求；
4. 当前 Skill 规则；
5. 各专业 Agent 的结构化结果；
6. Runtime / QA 的确定性结果。

## 4.6 Host Agent 的输出

Host Agent 主要输出：

- 用户要求摘要；
- Approved Outline；
- Wireframe；
- 页面视觉设计要求；
- 页面设计图片集；
- 专业 Agent 调用请求；
- Issue 分类；
- 交付状态；
- 最终交付物。

---

# 5. Approved Content 权威规则

## 5.1 Approved Outline

当用户确认大纲后：

```text
Approved Outline
```

成为后续内容规划的权威来源。

## 5.2 Approved Slide Content

每页进入正式设计与重建阶段时，应有明确的：

```text
Approved Slide Content
```

其内容来源于 Approved Outline 及用户后续明确确认的文字。

## 5.3 确认后的内容不可被下游改写

Approved Slide Content 确认后：

以下角色均不得改写内容：

- Host Agent；
- Layout Planner；
- Visual Reviewer；
- Runtime。

允许的仅包括：

- 换行；
- 断句位置调整；
- 文本框拆分；
- 不改变原文字面的版面适配。

不允许：

- 重写措辞；
- 替换同义词；
- 摘要压缩；
- 删除内容；
- 新增实质内容；
- 改变数字；
- 改变专有名词；
- 改变结论。

## 5.4 内容与版式冲突

若发现内容过长或与当前版式冲突：

```text
不得擅自改写
↓
优先调整布局
↓
仍无法解决
→ 返回 Host
→ 必要时重新与用户确认内容
```

---

# 6. Wireframe 能力归属

## 6.1 负责人

Wireframe 规划由 Host Agent 完成。

第一版不建立独立 Wireframe Planner Agent。

## 6.2 Wireframe 负责

Host Agent 应基于：

- Approved Outline；
- Approved Slide Content；
- 用户视觉要求；

规划：

- 页面信息分区；
- 标题区；
- 正文区；
- 图片区；
- 图表区；
- 关系结构；
- 相对位置；
- 区域比例；
- 信息层级；
- 页面视觉重心。

## 6.3 Wireframe 输出

Wireframe 应能够被确定性渲染器转换为：

- PNG；
- SVG；
- 其他可查看的线稿预览。

## 6.4 Wireframe 不负责

Wireframe 阶段不负责：

- 最终配色；
- 最终字体风格；
- 最终插图；
- 最终艺术效果；
- PPT 对象拆解；
- PPT 视觉审核。

---

# 7. 页面视觉设计能力归属

## 7.1 负责人

页面视觉设计由 Host Agent 负责。

Host Agent 可以调用当前宿主环境可用的：

- 图片生成模型；
- 图像编辑工具；
- 其他视觉生成能力。

第一版不建立独立 Visual Designer Agent。

## 7.2 设计输入

视觉设计应基于：

- Approved Slide Content；
- Wireframe；
- 用户视觉要求；
- Deck 整体视觉方向。

## 7.3 设计输出

输出：

```text
Page Design Image
```

作为：

- 用户视觉确认依据；
- Layout Planner 的视觉输入；
- Reviewer 的参考基准。

## 7.4 设计图不是文字权威源

即使设计图片中包含文字：

> Approved Slide Content 仍然是文字的权威来源。

设计图中的文字只用于：

- 元素定位；
- 样式判断；
- 空间关系判断。

---

# 8. Layout Planner 契约

## 8.1 角色定位

Layout Planner 是专门负责：

> 将既定页面设计图拆解并规划为可编辑 PowerPoint 对象结构。

它不是页面设计者，也不是 PPT Builder。

## 8.2 Layout Planner 的正式输入

Layout Planner 应接收：

1. 页面设计图；
2. Approved Slide Content；
3. 当前页面可用资产；
4. 用户视觉约束；
5. 可编辑性规则；
6. 页面尺寸 / 比例；
7. 必要的重建规范。

其中：

> Approved Slide Content 是文字权威来源。

## 8.3 Layout Planner 可以做

Layout Planner 可以：

- 识别页面视觉元素；
- 判断元素类型；
- 判断 native text / shape / line / image；
- 判断元素 bbox；
- 判断 z-order；
- 判断字体和字号；
- 判断填充和描边；
- 判断图片资产引用；
- 判断箭头和连接线关系；
- 判断文本框结构；
- 生成 Initial Reconstruction Specification；
- 根据 Reviewer issue 生成 Targeted Patch。

## 8.4 Layout Planner 不可以做

Layout Planner 不可以：

- 改写 Approved Slide Content；
- 根据 OCR 替换权威文字；
- 重新设计页面；
- 重新规划大纲；
- 修改用户确认的页面目标；
- 自己构建最终 PPT；
- 自己宣布视觉审核通过；
- 安装或修复 Python / Node 依赖；
- 选择或切换系统 Python 解释器；
- 检测或修复 Microsoft PowerPoint / PowerPoint COM；
- 因局部问题无理由重新规划整页。

## 8.5 OCR 限制

若设计图中存在文字：

```text
OCR / Vision text
```

只能作为辅助定位信息。

当 OCR 与 Approved Slide Content 冲突时：

> 必须使用 Approved Slide Content。

## 8.6 Layout Planner 的输出

输出应是结构化重建规格，至少表达：

- element id；
- element type；
- text / asset reference；
- bbox；
- z-order；
- font；
- size；
- fill；
- stroke；
- connector relation；
- editable / raster strategy；
- 必要的对象属性。

具体 Schema 在后续详细设计中定义。

## 8.7 Initial 与 Patch 两种输出模式

Layout Planner 应支持：

### Initial Planning

```text
Design Image
→ Full Reconstruction Spec
```

### Targeted Patch

```text
Current Spec
+
Reviewer / QA Issues
→ Patch
```

Patch 只修改受影响元素，不默认输出整页新规格。

---

# 9. Builder / Runtime 交接契约

## 9.1 角色定位

Builder / Runtime 不是 Agent。

它是确定性执行与环境管理子系统，负责两类生命周期：

```text
环境生命周期
Install / Bootstrap / Verify / Fast Preflight / Repair

任务生命周期
Asset Processing / Build / Render / Structural QA / Patch / Deck Assembly
```

## 9.2 环境阶段输入

环境阶段主要输入：

- Skill 版本与依赖锁定信息；
- 当前操作系统和架构；
- 可用 Python / Node；
- Microsoft PowerPoint 与 PowerPoint COM 状态；
- Runtime Manifest；
- 必要系统能力。

## 9.3 环境阶段负责

Runtime 负责：

- Managed Runtime Bootstrap；
- Python / Node 项目依赖验证；
- Runtime Manifest；
- Full Verify / Smoke Test；
- Fast Preflight；
- Runtime Repair；
- Microsoft PowerPoint detection 与 PowerPoint COM verification；
- Runtime `ready` / `environment_failure` 状态。

## 9.4 Runtime Ready Gate

对于需要进入图片到可编辑 PPT 重建的任务：

```text
Runtime Ready
↓
Layout Planner
```

如果 Runtime 未 Ready：

```text
Host
→ Bootstrap / Repair
→ Reverify
├─ Ready → Layout Planner
└─ Fail → environment_failure
```

Host 不得绕过该 Gate。

## 9.5 任务阶段输入

任务阶段主要输入：

- Layout Planner 输出的 Reconstruction Spec；
- Approved Slide Content；
- 页面资产；
- 页面尺寸与构建约束。

## 9.6 任务阶段负责

Runtime 负责：

- PPT 对象创建；
- 资产处理；
- 字体处理；
- PPTX 生成；
- Microsoft PowerPoint COM 渲染；
- 结构 QA；
- 基础可编辑性检查；
- Patch 应用；
- 多页合并；
- Deck 检查。

## 9.7 Runtime 不可以做

Runtime 不可以：

- 自行改写内容；
- 自行重新规划布局；
- 自行改变视觉目标；
- 用整页截图规避构建失败；
- 在技术错误时自动请求重新生成内容；
- 把 Runtime Repair 计入 Visual Revision；
- 因环境问题自动触发新的 Layout Planner 语义调用；
- 无边界修改用户系统级 Python / Node 配置。

---

# 10. Visual Reviewer 契约

## 10.1 角色定位

Visual Reviewer 是独立审核角色。

它负责：

> 比较页面设计图与 PowerPoint 实际渲染图，识别视觉还原问题。

## 10.2 独立性

Visual Reviewer 必须与 Layout Planner 使用独立上下文。

Reviewer 不得依赖 Planner 对自己结果的自我评价。

## 10.3 Reviewer 的最小输入

Reviewer 应看到：

1. 原始页面设计图；
2. PowerPoint 实际渲染图；
3. Approved Slide Content 摘要；
4. 结构 QA 摘要；
5. 页面元素简表；
6. 视觉审核规则。

## 10.4 Reviewer 不应看到

Reviewer 默认不应看到：

- Layout Planner 完整对话；
- Layout Planner 私有推理；
- Host Agent 对结果的主观评价；
- “该页面预期通过”之类结论性提示；
- 与审核无关的完整调试日志；
- 不必要的历史上下文。

目的是：

> 保持独立、减少上下文污染、降低调用成本。

## 10.5 Reviewer 可以做

Reviewer 可以：

- 判断视觉差异；
- 判断 issue severity；
- 标记受影响元素；
- 描述问题位置；
- 给出修改方向；
- 输出 `pass`；
- 输出 `revise`；
- 输出 `critical`。

## 10.6 Reviewer 不可以做

Reviewer 不可以：

- 直接修改 PPT；
- 直接修改 Reconstruction Spec；
- 改写 Approved Slide Content；
- 替代 Host 决定最终 delivery；
- 忽略结构 QA 已明确指出的硬性错误；
- 安装、切换或修复 Python / Node / Office Runtime；
- 因视觉差异自行重新设计整页。

## 10.7 Reviewer 输出

Reviewer 输出至少应包含：

```text
status
severity
issue_id
target_element_ids
observation
requested_change
evidence_region
```

具体 Schema 后续定义。

---

# 11. Reviewer Issue 交接规则

Reviewer 发现问题后：

```text
Visual Reviewer
↓
Structured Issues
↓
Host Agent
↓
问题分类
```

## 11.1 PPT 重建问题

例如：

- 坐标偏移；
- 卡片尺寸不对；
- 箭头接错；
- 图片裁切错误；
- 字体大小错误。

路由：

```text
Host
→ Layout Planner
→ Targeted Patch
→ Runtime
→ Render
→ Reviewer
```

## 11.2 页面设计本身问题

例如：

- 原设计图布局本身有明显逻辑问题；
- 用户要求与当前视觉设计不一致；
- 页面视觉策略需要调整。

路由：

```text
Host
→ 回视觉设计阶段
→ 重新生成受影响页面设计图
```

## 11.3 内容问题

例如：

- 设计图遗漏用户确认内容；
- 内容与 Approved Slide Content 冲突。

路由：

```text
Host
→ 不允许下游自行改写
→ 返回内容确认 / 用户
```

## 11.4 技术 / 环境问题

例如：

- Renderer 异常；
- Builder 异常；
- 字体审计异常；
- Fast Preflight 失败；
- Runtime 依赖损坏；
- Microsoft PowerPoint 或 PowerPoint COM 暂时不可用。

路由：

```text
Host
→ Runtime technical retry / Runtime Repair
→ Reverify
```

不得因此自动重新调用 Layout Planner，也不得消耗视觉定向修订次数。

---

# 12. 定向修订契约

## 12.1 最大次数

用户模式最多允许：

> 2 次定向视觉修订。

## 12.2 修订原则

每次修订必须：

- 对应明确 issue；
- 有 target element；
- 有 requested change；
- 尽量只修改受影响区域；
- 不改变 Approved Slide Content；
- 不无理由重新规划整页。

## 12.3 修订后

修订后应：

```text
Patch
→ 受影响阶段重跑
→ PowerPoint Render
→ Structural QA
→ Visual Reviewer
```

---

# 13. 最终交付权契约

## 13.1 所有者

最终交付状态由：

> Host Agent

决定。

但 Host Agent 必须依据固定 Gate，不能凭主观判断越过 QA 或 Reviewer。

## 13.2 Reviewer 的权限

Reviewer 只提供：

```text
pass
revise
critical
```

不直接输出：

```text
delivered
```

## 13.3 正常交付

满足：

```text
Structural QA = pass
+
Visual Reviewer = pass
```

则：

```text
delivered
```

## 13.4 带警告交付

满足：

- Structural QA = pass；
- 内容准确性 = pass；
- 可编辑性 = pass；
- Reviewer 已尝试调用；
- Reviewer 因技术原因超时 / 不可用；
- 没有已知 Major / Critical issue。

则：

```text
delivered_with_warnings
```

并明确：

```text
visual review incomplete
```

## 13.5 需要修订

Reviewer 正常返回：

```text
revise
```

则：

```text
revision_required
```

由 Host 路由定向修订。

## 13.6 失败

出现以下情况：

- 关键内容错误无法修复；
- 主要文字无法保持可编辑；
- 整页栅格化规避；
- Reviewer critical 且无法修复；
- 超过允许修订次数仍存在阻塞问题；
- 不可恢复技术故障；

则：

```text
failed
```

---

# 14. 上下文隔离规则

## 14.1 Host Agent

Host 可以看到完整任务级上下文。

## 14.2 Layout Planner

应只获得当前页面重建所需上下文。

不应携带：

- 无关页面历史；
- 用户全部长对话；
- Reviewer 不相关历史；
- Deck 其他无关信息。

## 14.3 Visual Reviewer

必须使用最小独立上下文。

重点保证：

- 与 Layout Planner context 隔离；
- 不传递 Planner 私有推理；
- 不传递预设结论；
- 不让 Reviewer 受到“应该通过”的暗示。

---

# 15. 多页并行交接规则

## 15.1 页面独立性

页面在满足依赖后可以独立执行：

```text
Slide 01
Slide 02
Slide 03
...
```

## 15.2 并行不得破坏

- 页面顺序；
- 页面资产归属；
- 页面状态；
- Agent context；
- Reviewer issues；
- Patch 归属；
- 最终 Deck 顺序。

## 15.3 单页失败

单页失败：

> 不应自动中断其他独立页面。

Host 应记录失败页面，并允许其他页面继续。

---

# 16. 角色禁止越权总结

| 行为 | Host | Layout Planner | Visual Reviewer | Runtime |
|---|---:|---:|---:|---:|
| 大纲确认前修改内容 | ✅ | ❌ | ❌ | ❌ |
| 大纲确认后改写内容 | ❌ | ❌ | ❌ | ❌ |
| Wireframe 规划 | ✅ | ❌ | ❌ | ❌ |
| 最终视觉设计 | ✅ | ❌ | ❌ | ❌ |
| PPT 重建规划 | 调度 | ✅ | ❌ | ❌ |
| PPT 实际构建 | 调度 | ❌ | ❌ | ✅ |
| 结构 QA | 调度 | ❌ | 读取摘要 | ✅ |
| 独立视觉审核 | 调度 | ❌ | ✅ | ❌ |
| 直接修改 PPT | ❌ | ❌ | ❌ | ✅ |
| Runtime readiness 检查 / Repair 调度 | ✅ | ❌ | ❌ | ✅（执行） |
| Reviewer issue 分类 | ✅ | ❌ | 仅报告 | ❌ |
| 最终 delivery 状态 | ✅（按 Gate） | ❌ | ❌ | 提供确定性结果 |

---

# 17. 标准交接流程

## 17.1 Content-to-PPT

```text
用户
↓
Host
↓
Runtime Fast Preflight
├─ Ready → 继续
└─ Not Ready → Bootstrap / Repair → Reverify
↓
候选大纲
↓
用户确认
↓
Approved Outline / Approved Slide Content
↓
Host Wireframe
↓
Host Visual Design / Image Generation
↓
Design Image
↓
Runtime Ready Gate
↓
Layout Planner
↓
Reconstruction Spec
↓
Runtime Build
↓
Render + Structural QA
↓
Visual Reviewer
↓
Issues / Pass
↓
Host
├─ Pass → Delivery Gate
├─ Reconstruction Issue → Layout Planner Patch
├─ Design Issue → Visual Design Stage
├─ Content Issue → User / Content Confirmation
└─ Reviewer Technical Failure → Warning Delivery Gate
```

## 17.2 Image-to-Editable-PPT

```text
用户页面图片
↓
Host
↓
Runtime Fast Preflight
├─ Ready → 继续
└─ Not Ready → Bootstrap / Repair → Reverify
↓
Layout Planner
↓
Reconstruction Spec
↓
Runtime
↓
Render + Structural QA
↓
Visual Reviewer
↓
Host Delivery Gate
```

---

# 18. 第一版冻结角色

第一版正式冻结为：

```text
1. Host Agent
2. Layout Planner
3. Visual Reviewer
```

其中：

- Host Agent = Claude Code / Codex 等宿主；
- Layout Planner = Skill 内专业重建 Agent；
- Visual Reviewer = Skill 内独立审核 Agent。

第一版不增加其他专业 Agent，除非后续测试能够证明拆分具有明确质量或性能收益。

---

# 19. 最终契约定义

`Content to Editable PPT Skill` v1.2 的 Agent 协作原则可以概括为：

> Host Agent 负责理解用户、规划内容、规划 Wireframe、组织视觉设计并控制整个流程；Layout Planner 专门负责将既定页面设计图转化为可编辑 PowerPoint 重建规格；Visual Reviewer 以最小独立上下文对最终渲染结果进行独立视觉审核。用户确认后的内容是下游不可改写的权威来源，Reviewer 只报告问题、不直接修改，最终交付由 Host 按固定 Gate 决定。通过这种职责分离，第一版在保留完整 PPT 设计流程的同时避免不必要的 Agent 数量和模型调用。
