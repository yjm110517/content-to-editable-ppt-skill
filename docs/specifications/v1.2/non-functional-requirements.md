# Content to Editable PPT Skill 非功能需求与质量指标 v1.2


## v1.2 变更摘要

本版本在 v1.1 Runtime 可复现性、依赖隔离和错误恢复要求基础上，同步总体架构 v2.0 的 Windows-only 质量基线。

主要变化：

- Supported OS 固定为 Windows；
- Required Office Runtime 固定为 Microsoft PowerPoint Desktop；
- Required Automation 固定为 PowerPoint COM；
- 取消 Full Fidelity / Compatible / Degraded Backend 分级作为当前 MVP 验收要求；
- 环境问题必须在 Layout Planner 前进入 `environment_failure`；
- 保留未来增加其他 Backend 的架构扩展性，但不将其列入 v2.0 发布 Gate。

---

## 1. 文档目的

本文档定义 `Content to Editable PPT Skill` 第一版的非功能需求（Non-Functional Requirements, NFR）与质量指标，用于约束内容准确性、可编辑性、视觉质量、性能、稳定性、并行执行、Reviewer 降级策略、Agent 兼容性与可维护性。

本文档回答：

> 已定义的功能需要达到什么质量、稳定性和执行效率，什么结果可以接受，什么结果不能接受。

本文档不规定：

- 具体脚本名称；
- JSON Schema 字段；
- Agent YAML 配置；
- Prompt 具体实现；
- 模型型号；
- 线程、进程或并发数；
- PowerPoint COM / OOXML 的具体实现；
- Runtime 状态机字段。

上述内容由 Agent 契约、Runtime 执行规范、架构设计和详细实现文档定义。

---

# 2. 总体质量优先级

第一版正式质量优先级为：

```text
内容准确性
>
可编辑性
>
视觉质量
>
运行速度
```

该优先级用于解决不同目标之间的冲突。

## 2.1 冲突处理原则

### 内容准确性 vs 视觉质量

必须优先保证内容准确。

不得为了：

- 页面更美观；
- 文字更短；
- 版式更整齐；
- 视觉更接近设计图；

而擅自修改用户确认后的内容。

### 可编辑性 vs 像素级还原

必须优先保证主要文字和主要结构可编辑。

允许为了可编辑性接受少量视觉偏差，但不能无理由明显降低视觉质量。

### 视觉质量 vs 运行速度

不得为了单纯缩短时间而取消：

- 必要的页面布局规划；
- 页面视觉设计；
- 结构 QA；
- 独立 Visual Reviewer；
- 必要的定向修订。

性能优化的主要目标是消除无质量收益的重复工作。

---

# 3. NFR-01 内容准确性

## 3.1 目标

确保用户确认后的内容在后续布局、视觉设计、图片生成、PPT 重建和审核阶段保持准确，不被模型、OCR 或视觉重建过程擅自改变。

## 3.2 已确认大纲的权威性

用户确认后的 Approved Outline 是后续内容生成的权威基准。

大纲确认后：

> 不允许继续改写已确认内容。

后续阶段允许做的只有：

- 断句；
- 换行；
- 文本框拆分；
- 不改变文字本身的版面适配。

后续阶段不允许：

- 重新总结；
- 改写措辞；
- 替换表达；
- 压缩已确认文字；
- 删除已确认内容；
- 增加新的实质性内容。

若后续发现内容过长或不适合当前版式，应：

```text
发现内容与版式冲突
→ 不擅自改写
→ 调整布局
或
→ 返回用户 / 上游内容阶段重新确认
```

## 3.3 强一致内容

以下内容要求与用户确认版本 100% 一致：

- 数字；
- 百分比；
- 日期；
- 专有名词；
- 人名；
- 机构名；
- 产品名；
- 引用；
- 结论；
- 用户明确要求保留的核心表述。

## 3.4 OCR 与视觉识别限制

当已有权威文本存在时：

> OCR、图像识别或视觉模型识别结果不得覆盖权威文本。

视觉识别只能用于：

- 布局判断；
- 元素定位；
- 样式识别；
- 无权威文本时的辅助识别。

## 3.5 禁止内容行为

禁止：

- 捏造事实；
- 捏造数据；
- 捏造引用；
- 捏造结论；
- 未经授权引入关键外部事实；
- 在确认后擅自重写正文。

---

# 4. NFR-02 可编辑性

## 4.1 目标

最终 PowerPoint 应满足：

> 主要文字和主要结构可编辑。

采用“标准 B”。

## 4.2 主要文字

主要文字要求：

> 100% 使用 PowerPoint 原生可编辑文本。

包括：

- 标题；
- 副标题；
- 正文；
- 标签；
- 数字；
- 图示中的主要文字；
- 主要说明文字。

主要文字不得通过以下方式替代：

- 截图；
- 页面图片；
- 将文字烧录进背景图片。

## 4.3 基础形状与结构

以下内容应在能够可靠实现时尽量原生化：

- 矩形；
- 圆形；
- 圆角矩形；
- 基础几何形状；
- 线条；
- 箭头；
- 连接线；
- 简单流程结构；
- 卡片；
- 基础表格；
- 适合 PowerPoint 原生表达的基础图表。

原则：

> 能够可靠原生化且不会显著破坏视觉效果时，应优先使用原生对象。

## 4.4 复杂视觉资产

以下内容允许图片化：

- 照片；
- 人物；
- 复杂插图；
- 艺术性视觉；
- 复杂纹理；
- 复杂背景元素；
- 难以可靠原生重建的复杂视觉对象。

## 4.5 整页栅格化

禁止：

> 使用整页图片、整页截图或整页设计图作为唯一页面内容，并将其作为“可编辑 PPT”交付。

整页图片不得用于规避：

- 文本原生化；
- 基础结构原生化；
- 编辑性要求。

---

# 5. NFR-03 视觉质量

## 5.1 目标

最终 PowerPoint 的实际渲染结果应与确认后的页面设计保持较高视觉一致性。

第一版不设置未经基准测试支持的固定视觉相似度百分比。

采用问题严重度作为主要交付判断依据。

## 5.2 不可接受问题

以下问题属于不可接受的 Major / Critical 视觉问题：

- 明显错位；
- 文字溢出；
- 字体层级明显错误；
- 箭头或连接线连接错误；
- 图片裁切明显错误；
- 大面积背景接缝；
- 页面风格明显漂移；
- 关键比例严重失真；
- 关键元素缺失；
- 主要视觉关系错误；
- 页面主要结构与确认设计明显不一致；
- 为规避可编辑性要求而整页栅格化。

存在上述问题时：

```text
不得按正常通过状态交付
→ 必须进入定向修订
或
→ 判定失败 / 带明确未完成状态
```

## 5.3 可接受 Minor 偏差

以下偏差在不影响整体视觉和信息表达时可以接受：

- 阴影略有差异；
- 渐变略有差异；
- 几个像素级的位置偏差；
- 复杂装饰没有完全复刻；
- 极细微的圆角或描边差异；
- 不影响内容层级的微小字体渲染差异。

仅存在 Minor 问题时允许正常交付。

## 5.4 视觉审核基本项

Reviewer 至少应覆盖：

- 页面整体布局；
- 关键比例；
- connector topology；
- connector endpoints；
- typography hierarchy；
- crop boundaries；
- background seams；
- visual depth；
- 主要元素位置；
- 页面视觉重心；
- 风格一致性；
- 内容遗漏；
- 编辑性规避。

---

# 6. NFR-04 Reviewer 与交付策略

## 6.1 Reviewer 必须调用

正式用户流程中：

> 最终页面必须尝试调用独立 Visual Reviewer。

负责页面重建的 Planner 不得自行替代最终 Reviewer。

## 6.2 Reviewer 正常返回

当 Reviewer 正常返回时：

- `pass`：进入交付或 Deck 整合；
- `revise`：进入定向修订；
- `critical failure`：不得正常交付。

## 6.3 最大定向修订次数

用户模式最多允许：

> 2 次定向视觉修订。

即：

```text
初始版本
→ Reviewer
→ Revision 1
→ Reviewer
→ Revision 2
→ Reviewer
→ 最终判断
```

不得形成无上限的 Reviewer / Planner 循环。

## 6.4 Reviewer 超时或不可用

采用降级交付策略：

```text
结构 QA 已通过
↓
必须尝试 Reviewer
↓
Reviewer 因技术原因超时 / 不可用
↓
不得因此重新调用 Planner
↓
允许带警告交付
```

降级交付必须明确标记：

```text
visual review incomplete
```

或等价状态。

## 6.5 降级交付边界

只有满足以下条件时允许降级交付：

- 结构 QA 已通过；
- 内容准确性检查通过；
- 可编辑性检查通过；
- Reviewer 失败原因属于技术不可用 / 超时，而不是 Reviewer 已发现 Major 问题。

如果 Reviewer 已正常返回并指出 Major / Critical 问题：

> 不允许使用“Reviewer 不完整”作为降级交付理由。

---

# 7. NFR-05 性能与流程效率

## 7.1 总运行时长

第一版：

> 不设置固定总时长上限。

不采用：

- 必须 5 分钟；
- 必须 8 分钟；
- 超过固定分钟数即失败；

等硬性总时长 SLA。

允许有效的质量修订增加运行时间。

## 7.2 性能优化目标

性能优化重点是消除：

- 重复 Planner 调用；
- 技术故障导致的重新规划；
- 局部错误导致的整页重做；
- 输入未变化时的重复构建；
- 不必要的资产重新处理；
- 无意义的 Reviewer 重复调用；
- 已通过阶段的重复执行。

同时应遵循“环境问题早发现”原则：

> 能够在安装、Verify 或 Fast Preflight 阶段发现的依赖与 Backend 问题，不应无意义拖延到 Layout Planner、Build 或 Render 之后才首次暴露。

正常任务不应因为每次执行都重新安装依赖而产生额外等待。

## 7.3 Planner 调用原则

正常单页初始规划：

> 原则上只进行一次 Initial Planner 调用。

技术错误不得增加语义 Planner 调用次数。

## 7.4 技术错误

技术错误：

> 禁止触发新的语义规划。

Environment Failure 与 Planner Failure 必须分离。Runtime Repair 不得增加 Layout Planner 语义调用次数，也不得消耗视觉定向修订额度。

例如：

- 构建器失败；
- 渲染器失败；
- 字体审计脚本异常；
- QA 脚本异常；
- 环境依赖错误；
- 资产处理工具异常。

应优先：

```text
修复技术问题
→ 复用现有规划结果
→ 从失败阶段恢复
```

## 7.5 局部错误

局部错误：

> 禁止默认整页重做。

优先采用：

```text
具体 issue
→ 定位受影响元素
→ 定向 Patch
→ 仅重跑受影响阶段
```

## 7.6 已通过阶段复用

当：

- 输入未变化；
- 上游权威内容未变化；
- 当前阶段产物已经通过；

应尽量复用既有成果。

## 7.7 性能可观测性

运行过程应能够记录或获得主要阶段耗时，至少包括：

- Planner；
- 资产处理；
- PPT 构建；
- 字体审计；
- PowerPoint 渲染；
- 结构 QA；
- Visual Reviewer；
- 修订。

同时应能识别：

- Planner 调用次数；
- Reviewer 调用次数；
- 技术重试次数；
- 语义修订次数；
- 定向修订次数。

---

# 8. NFR-06 稳定性与错误恢复

## 8.1 禁止无限重试

正式要求：

> 禁止无限重试。

所有自动重试必须：

- 有明确触发条件；
- 有次数限制；
- 有退出条件；
- 不允许无边界循环。

## 8.2 允许受控重试

可以存在：

- 有限制的技术重试；
- 最多 2 次视觉定向修订；
- 必要的环境恢复后继续执行。

但必须保证最终能够：

```text
成功
或
带警告交付
或
明确失败
```

## 8.3 失败必须分类

所有失败应能够归入明确类别。

至少区分：

- environment failure；
- technical failure；
- specification failure；
- content failure；
- visual review failure；
- unrecoverable failure。

不得长期使用：

```text
unknown error
→ retry everything
```

作为默认处理方式。

## 8.4 技术错误与内容错误分离

技术错误不得被解释为内容规划错误。

内容正确时：

> 不应因为构建、渲染或工具问题重新执行 Outline / Layout 的语义规划。

## 8.5 单页失败隔离

多页任务中：

> 单个页面失败允许其他独立页面继续处理。

不得因为一页失败：

- 删除其他已通过页面；
- 强制全部页面重新开始；
- 破坏其他页面状态。

## 8.6 恢复原则

失败后应尽可能：

```text
保留已完成产物
→ 定位失败阶段
→ 修复
→ 从合理阶段继续
```

而不是：

```text
失败
→ 删除全部结果
→ 从头开始
```

## 8.7 Runtime Repair

Fast Preflight 发现可修复的环境问题时，应优先执行：

```text
Runtime Repair
→ Reverify
→ Resume
```

Runtime Repair：

- 不消耗 Visual Reviewer 的两次定向修订额度；
- 不增加 Layout Planner semantic revision；
- 不删除已确认的大纲与页面内容；
- 不将环境故障误判为内容或视觉规划失败。

若 Repair 后仍无法达到任务所需能力，应产生明确的 `environment_failure`，而不是无限重试。

---

# 9. NFR-07 多页面并行与隔离

## 9.1 并行能力

在依赖条件满足时：

> 独立页面允许并行执行。

功能与架构不得强制所有页面完全串行。

## 9.2 并行前置条件

页面进入并行执行前应满足：

- 大纲已确认；
- 当前页面内容已确定；
- 当前页面设计输入已准备；
- 与其他页面不存在必须串行的业务依赖。

## 9.3 并行隔离

并行不得影响：

- 页面顺序；
- 页面状态；
- Agent 上下文隔离；
- 页面资产隔离；
- Reviewer 结果归属；
- 最终 Deck 顺序；
- 单页错误隔离。

## 9.4 并发数量

第一版 NFR 不固定：

- 最大并发数；
- 线程数；
- 进程数；
- 同时 Agent 数。

具体并发策略应通过后续性能测试和实际运行环境确定。

---

# 10. NFR-08 Agent 与平台兼容性

## 10.1 第一版必须支持的宿主 Agent

第一版正式兼容目标：

- Claude Code；
- Codex。

## 10.2 Agent 兼容原则

核心 Skill 工作流不得依赖：

- 单一 Agent 的私有 UI；
- 单一 Agent 的专有对话状态；
- 只存在于一个产品中的不可替代内部机制。

## 10.3 基础能力假设

宿主 Agent 至少应具备：

- 文件系统访问；
- 命令执行；
- 用户交互；
- 模型或工具调用；
- 基础上下文管理能力。

## 10.4 Agent 兼容性与 Windows Runtime 分离

必须明确：

```text
Host Agent 可执行 Skill
≠
当前机器具备完全相同的 PowerPoint 自动化能力
```

第一阶段的正式 Runtime 必须同时满足：

```text
Windows
+ Microsoft PowerPoint Desktop
+ PowerPoint COM
```

任一条件不满足时，Runtime 必须在 Layout Planner 调用前返回 `environment_failure`。macOS、Linux、LibreOffice 与其他 Backend 为 Future Work，不属于当前 Release Gate。

## 10.5 其他 Agent

其他具备类似能力的 Agent：

> 作为后续兼容目标。

第一版不承诺对所有 Agent 完成正式验证，但架构应避免人为阻止后续兼容。

---

# 11. NFR-09 可维护性

## 11.1 Agent 职责分离

不同 Agent 应保持清晰职责。

第一版角色边界为：

- Host Agent 负责内容理解、大纲规划、Wireframe、视觉设计调度与流程编排；
- Layout Planner 负责页面重建规划与 Targeted Patch；
- Visual Reviewer 负责独立视觉审核；
- Runtime / Scripts 负责确定性构建、渲染、QA、Bootstrap、Preflight 与 Repair。

不得为了形式上的“多 Agent 化”把每个功能阶段都拆成独立 Agent，也不得让专业 Agent 越权承担环境管理或最终交付判断。

## 11.2 语义任务与确定性任务分离

优先原则：

```text
需要理解 / 设计 / 判断
→ 模型或 Agent

可以确定执行
→ 脚本
```

例如：

- 内容规划适合 Agent；
- 页面渲染适合确定性工具；
- 文件校验适合脚本；
- 视觉判断适合 Reviewer。

## 11.3 避免重复实现

多页能力应尽量复用成熟的单页 Runtime。

不得为了 Deck 功能重新复制一套单页：

- Builder；
- Renderer；
- QA；
- Reviewer；
- Asset pipeline。

## 11.4 状态权威性

同一层级不应存在多个相互冲突的权威状态来源。

派生报告可以存在，但不得与主状态产生双重控制。

---

# 12. NFR-10 可观测性与诊断

## 12.1 内部运行记录

用户模式可以减少公开日志，但内部应保留足够的诊断信息。

至少应能够确认：

- 当前阶段；
- 当前页面；
- Agent 调用角色；
- Agent 调用结果；
- 失败类型；
- 重试次数；
- 修订次数；
- Reviewer 状态；
- 主要耗时。

## 12.2 用户公开交付与内部诊断分离

默认用户交付：

```text
outline
design images
editable PPTX
```

默认不需要公开：

- QA 原始报告；
- Agent call records；
- 内部状态；
- Debug 日志；
- 中间构建文件。

但开发模式或诊断场景应能够访问这些信息。

---

# 13. NFR-11 Runtime 可复现性与依赖隔离

## 13.1 目标

Skill 应维护并验证自身受控运行环境，避免普通任务依赖用户机器中任意、不可预测的全局 Python / Node 包状态。

## 13.2 Python 依赖隔离

项目 Python 依赖应尽量位于 Skill 管理的隔离环境中。

正常运行不得要求用户在多个全局 Python 环境之间反复尝试。

## 13.3 Node 依赖隔离

项目 Node 依赖应采用项目级依赖与锁文件。

不得把用户全局 npm 包作为正常执行的唯一前提。

## 13.4 依赖可复现性

Python / Node 正式依赖应有可复现的版本来源或锁定清单。

应避免每次安装自动使用任意最新版本而导致不同机器行为不可预测。

## 13.5 Runtime Manifest

Runtime 应能够记录当前环境至少包括：

- Skill version；
- OS / architecture；
- Python executable / version；
- Python dependency state；
- Node executable / version；
- Node dependency state；
- Microsoft PowerPoint version / availability；
- PowerPoint COM verification status；
- verify status。

Runtime Manifest 是环境级状态，不得与任务级 `run_state` 混为同一权威状态。

## 13.6 Bootstrap 与 Verify

安装或首次运行时，应能够完成：

```text
Bootstrap
→ Verify
→ Ready / Environment Failure
```

完整 Verify 不应只验证 import 成功，还应至少通过最小 PPT Smoke Test 验证核心 Runtime 实际可工作。

## 13.7 Fast Preflight

需要进入图片到可编辑 PPT 重建的任务，在 Layout Planner 调用前必须完成 Fast Preflight。

Fast Preflight 应优先快速验证已建立 Runtime，而不是每次重做完整安装。

## 13.8 Runtime Repair

可修复的 Runtime 问题应优先通过受控 Repair 解决。

Repair：

- 不消耗视觉修订额度；
- 不触发新的 Layout Planner 语义规划；
- 不改变 Approved Content；
- 修复后必须重新 Verify / Preflight。

## 13.9 Windows Runtime 强制要求

当前 MVP 不定义 Backend 能力分级。Runtime 只能在 Windows、Microsoft PowerPoint Desktop 和 PowerPoint COM 全部验证通过后标记为 `ready`。

架构不应无必要地阻止未来增加其他 Backend，但此扩展性不是 v2.0 验收标准。

---

# 14. 质量 Gate 总结

## 14.1 正常交付

满足：

- 内容准确；
- 主要文字 100% 可编辑；
- 主要结构满足编辑性要求；
- 结构 QA 通过；
- Reviewer 正常通过；
- 不存在 Major / Critical 视觉问题。

状态可视为：

```text
delivered
```

## 14.2 带警告交付

满足：

- 内容准确；
- 可编辑性检查通过；
- 结构 QA 通过；
- Reviewer 已尝试调用；
- Reviewer 因技术原因超时或不可用；
- 没有已知 Major / Critical 问题。

状态可视为：

```text
delivered_with_warnings
```

并明确：

```text
visual review incomplete
```

## 14.3 需要修订

Reviewer 正常返回并发现可修复 Major 问题：

```text
revision_required
```

最多进行 2 次定向修订。

## 14.4 失败

以下情况不得正常交付：

- 关键内容错误无法修复；
- 主要文字无法保持可编辑；
- 整页栅格化规避编辑性要求；
- PowerPoint 无法正常打开或渲染；
- Reviewer 已确认存在 Critical 问题且修订后仍未解决；
- 发生不可恢复故障。

状态：

```text
failed
```

---

# 15. 第一版核心 NFR 验收项

第一版至少应验证：

1. Approved Outline 确认后，后续阶段不会擅自改写文字；
2. 数字、专有名词、结论能够保持 100% 一致；
3. 主要文字全部为 PowerPoint 原生文本；
4. 基础形状能够原生化时优先原生化；
5. 复杂视觉允许图片化；
6. 不出现整页图片冒充可编辑 PPT；
7. Major 视觉问题不会被正常标记为通过；
8. Minor 视觉差异允许交付；
9. Reviewer 每次最终页面都会被尝试调用；
10. Reviewer 技术超时时不会重新调用 Planner；
11. Reviewer 技术超时时，结构 QA 通过可带警告交付；
12. 用户模式最多 2 次定向视觉修订；
13. 不设置固定总运行时长上限；
14. 技术错误不会触发语义 Planner 重跑；
15. 局部错误不会默认导致整页重做；
16. 输入未变化的已通过阶段能够复用；
17. 不存在无限重试；
18. 所有主要失败能够分类；
19. 单页失败不会无理由阻断其他独立页面；
20. 多页面允许并行且不破坏页面顺序和状态隔离；
21. Claude Code 与 Codex 均作为正式兼容目标；
22. 核心 Skill 流程不绑定单一 Agent 私有机制；
23. Skill 能够建立并验证受控 Runtime；
24. 正常运行不依赖用户全局 Python / npm 包状态作为唯一前提；
25. 需要重建的任务在 Layout Planner 前完成 Fast Preflight；
26. 可在 Preflight 发现的环境问题不会无意义拖延到 Build / Render 后才首次暴露；
27. Runtime Repair 不增加 Layout Planner 语义调用，也不消耗视觉修订次数；
28. 无法修复的环境问题产生明确 `environment_failure`；
29. Runtime Manifest 与任务 `run_state` 明确分离；
30. Windows、Microsoft PowerPoint 和 PowerPoint COM 中任一条件不满足时，Planner 调用数为 0 并产生明确 `environment_failure`。

---

# 16. 最终非功能需求定义

`Content to Editable PPT Skill` v1.2 的非功能目标可以概括为：

> 在内容准确性优先的前提下，保证主要文字和主要结构可编辑，并通过独立视觉审核维持较高页面质量；同时通过受控重试、局部修复、阶段复用、多页面并行和明确失败分类，减少无效重复工作。Skill 应维护可验证、可修复的受控 Runtime，并在 Layout Planner 前完成环境可用性 Gate，避免可提前发现的环境问题造成无意义 Agent 等待。系统不设置固定总运行时长上限，但禁止无限循环和无质量收益的重复执行。第一版正式面向 Claude Code 与 Codex，并保持核心工作流对其他兼容 Agent 可扩展。
