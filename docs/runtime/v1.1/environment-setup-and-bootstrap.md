# Content to Editable PPT Skill 运行环境安装与引导规范 v1.1

> 英文名：Runtime Installation & Bootstrap Specification v1.1

## v1.1 变更摘要

本版本同步总体架构 v2.0 的 Windows-only 决策，将第一阶段 Runtime 收敛为 Windows、Microsoft PowerPoint Desktop 和 PowerPoint COM。

主要变化：

- 唯一安装入口为 `install.ps1`；
- 移除 macOS、Linux、LibreOffice 与 Compatible Backend 的 MVP 实现要求；
- Bootstrap 必须检测 Microsoft PowerPoint 并验证 PowerPoint COM；
- Runtime 结果收敛为 `ready` 或 `environment_failure`；
- 其他平台和 Backend 仅作为 Future Work。

## 1. 文档目的

本文档定义 `Content to Editable PPT Skill` 的运行环境安装、首次初始化（Bootstrap）、依赖隔离、运行能力检测、安装验证、快速预检（Fast Preflight）以及运行环境自动修复（Runtime Repair）规则。

本文档解决的问题是：

> 如何让 Claude Code、Codex 等宿主 Agent 在安装 Skill 后，尽可能无需用户手工寻找 Python、Node、项目依赖或运行路径，即可直接执行 Skill。

本文档主要覆盖：

- Skill 安装后的 Runtime 准备；
- Python / Node 依赖隔离；
- 依赖版本锁定；
- Microsoft PowerPoint Desktop 与 PowerPoint COM 检测；
- Runtime Manifest；
- 首次安装验证；
- 日常快速预检；
- Runtime 损坏后的自动修复；
- Windows-only Runtime Ready Gate；
- 安装失败和修复失败时的行为。

本文档不定义：

- 单页 PPT 的具体重建流程；
- Layout Planner Prompt；
- Visual Reviewer Prompt；
- Reconstruction Spec Schema；
- run_state 结构；
- 单页视觉修订规则；
- Deck 合并实现细节。

上述内容由其他 Runtime、Agent、Artifact 和架构文档定义。

---

# 2. 设计目标

## 2.1 核心目标

Skill 应尽可能实现：

```text
安装 Skill
↓
自动准备运行环境
↓
自动验证
↓
READY
↓
Claude Code / Codex 直接调用
```

而不是：

```text
安装 Skill
↓
用户手工找 Python
↓
手工安装依赖
↓
手工找 Node
↓
手工安装 npm 包
↓
手工测试 PowerPoint
↓
反复排错
```

## 2.2 运行环境应由 Skill 管理

Skill 不应把正常运行建立在以下不稳定前提上：

- 用户当前默认 `python` 恰好正确；
- 用户全局 Python 已安装全部依赖；
- 用户当前默认 `node` 版本恰好兼容；
- 用户全局 npm 环境已安装 `pptxgenjs`；
- 用户自己知道哪个虚拟环境可以运行；
- 每次任务都临时寻找一个可用环境。

原则：

> Skill 应维护并验证自身受控运行环境，而不是依赖任意系统全局环境。

## 2.3 环境问题必须尽量在语义 Agent 调用前发现

任何能够在安装或 Preflight 阶段发现的问题，不应拖延到：

- Layout Planner 已完成；
- PPT Build 已开始；
- Render 已开始；

之后才首次发现。

目标是避免：

```text
Planner运行十几分钟
↓
Build
↓
才发现 Python 包缺失
```

---

# 3. Runtime 生命周期

Runtime 生命周期分为四个阶段：

```text
Install
↓
Bootstrap
↓
Verify
↓
Ready
```

正常使用时：

```text
Task Start
↓
Fast Preflight
├─ Ready → 进入任务 Runtime
└─ Not Ready
     ↓
 Runtime Repair
     ↓
 Reverify
 ├─ Pass → 进入任务 Runtime
 └─ Fail → Environment Failure
```

---

# 4. Skill 安装阶段

## 4.1 安装目标

安装阶段至少需要完成：

1. 将 Skill 文件安装到宿主 Agent 可识别位置；
2. 检测操作系统和 CPU 架构；
3. 准备受控 Runtime；
4. 准备 Python 依赖；
5. 准备 Node 依赖；
6. 检测 Microsoft PowerPoint Desktop 并验证 PowerPoint COM；
7. 检测必要字体和系统能力；
8. 执行 Smoke Test；
9. 生成 Runtime Manifest；
10. 标记安装状态。

## 4.2 典型安装入口

第一阶段只提供：

```text
install.ps1
```

`install.ps1` 负责：

- 安装 Skill；
- 检测 Windows 环境；
- Bootstrap Runtime；
- 检测 Microsoft PowerPoint；
- 检测 PowerPoint COM；
- 运行完整安装验证；
- 输出安装结果。

如当前系统不是 Windows，安装流程必须立即停止并返回明确的 `environment_failure`，不得尝试切换到兼容 Backend。

---

# 5. Managed Runtime

## 5.1 定义

Managed Runtime 指：

> 由 Skill 自己准备、定位、验证并复用的受控运行环境。

其目的不是替代操作系统，而是避免每次任务依赖不确定的全局 Python / Node 状态。

## 5.2 Python Runtime

Skill 应优先：

```text
检测兼容 Python
↓
创建 Skill 专用虚拟环境
↓
安装锁定依赖
↓
验证
```

Python 项目依赖不应默认安装到用户全局 site-packages。

典型依赖包括但不限于：

- `python-pptx`
- `Pillow`
- `PyYAML`
- `jsonschema`
- `pywin32`（PowerPoint COM 自动化必需）
- Skill 其他正式依赖

具体依赖清单由项目锁文件决定。

## 5.3 Node Runtime

Node 部分应采用项目级依赖：

```text
Skill
↓
package.json / lock file
↓
node_modules
```

典型依赖包括：

- `pptxgenjs`
- 其他正式构建依赖

Skill 不应依赖用户全局 `npm install -g` 状态作为正常运行前提。

## 5.4 Python / Node 不存在时

安装器应遵循：

```text
优先使用可兼容的系统 Runtime
↓
不存在或不兼容
→ 尝试准备受控 Runtime
```

如果当前环境无法自动准备，则：

```text
明确报告缺失能力
→ 给出安装失败状态
```

不能进入后续语义 Agent 阶段。

---

# 6. 依赖锁定与可复现性

## 6.1 Python

Python 依赖应有明确版本来源，例如：

- requirements lock；
- 项目锁文件；
- 其他可复现依赖清单。

安装器应避免：

```text
每次安装
→ 自动拉取任意最新版本
```

导致不同机器行为不一致。

## 6.2 Node

Node 依赖应使用锁文件。

例如：

```text
package-lock.json
```

或项目最终选定的等价方案。

## 6.3 Runtime 版本信息

Runtime Manifest 应记录至少：

- Skill version；
- OS；
- architecture；
- Python executable；
- Python version；
- Python dependency state；
- Node executable；
- Node version；
- Node dependency state；
- Microsoft PowerPoint version / availability；
- PowerPoint COM verification status；
- verify status。

---

# 7. Microsoft PowerPoint Runtime

## 7.1 原则

PowerPoint 特定能力不应直接散落在业务流程中，但当前 MVP 的正式 Runtime 只有一个：

```text
Windows
+ Microsoft PowerPoint Desktop
+ PowerPoint COM
```

## 7.2 必需能力

该 Runtime 必须能够提供：

- PPTX 打开验证；
- PowerPoint 实际渲染；
- PowerPoint 自动化；
- 字体 / 页面渲染检查；
- Deck 合并或 Office 自动化能力。

## 7.3 Ready Gate

只有 Windows、Microsoft PowerPoint Desktop 和 PowerPoint COM 全部验证通过时，Runtime 才能记录：

```text
runtime_status = ready
```

任一条件不满足时必须产生 `environment_failure`。其他操作系统和 Backend 仅作为 Future Work，不得进入当前 Runtime 执行路径。

---

# 8. Bootstrap 流程

## 8.1 完整流程

建议 Bootstrap 顺序：

```text
01 Detect Windows / Architecture
↓
02 Resolve Skill Root
↓
03 Resolve Runtime Cache / Managed Runtime
↓
04 Resolve compatible Python
↓
05 Create / verify Python environment
↓
06 Install / verify Python locked dependencies
↓
07 Resolve compatible Node
↓
08 Install / verify Node locked dependencies
↓
09 Detect Microsoft PowerPoint Desktop
↓
10 Verify PowerPoint COM
↓
11 Detect key fonts / system capabilities
↓
12 Verify writable directories
↓
13 Run smoke tests
↓
14 Write runtime-manifest
↓
15 Mark READY
```

## 8.2 Bootstrap 的边界

Bootstrap 可以做：

- 创建虚拟环境；
- 安装项目依赖；
- 建立 Runtime Cache；
- 检测 Office 能力；
- 写入 Runtime Manifest；
- 修复缺失依赖。

Bootstrap 不应：

- 修改用户 PPT 内容；
- 调用 Layout Planner；
- 调用 Visual Reviewer；
- 修改项目业务数据；
- 随意覆盖用户全局 Python 配置；
- 随意修改用户系统级环境变量。

---

# 9. Full Verify

## 9.1 目标

验证：

> Runtime 不仅“安装了依赖”，而且真的能够完成最小 PPT 工作。

仅执行：

```text
import succeeded
```

不应视为完整安装成功。

## 9.2 Smoke Test

至少建议验证：

```text
创建最小PPT
↓
写入原生文本
↓
写入基础形状
↓
保存PPTX
↓
使用 Microsoft PowerPoint COM 打开/渲染
↓
检查输出
```

Windows + Microsoft PowerPoint 环境下，还应检查：

- PowerPoint COM 是否可创建；
- PowerPoint 是否能正常打开测试 PPTX；
- 渲染是否成功。

## 9.3 Verify 结果

只有两类对外结果：

```text
ready
environment_failure
```

### ready

受支持的 Windows、Microsoft PowerPoint 和 PowerPoint COM 能力全部可用。

### environment_failure

Runtime 初始化、Windows 检测、PowerPoint 检测或 COM 验证失败。具体原因必须作为诊断信息记录。

---

# 10. Runtime Manifest

## 10.1 目的

Runtime Manifest 用于记录：

> 当前 Skill 运行环境是什么，以及它是否已经通过验证。

它不是任务级状态。

## 10.2 与 run_state 的区别

```text
runtime-manifest
= Skill运行环境状态

run_state
= 当前某一页任务执行状态
```

两者不得混用。

## 10.3 Manifest 概念字段

示例：

```json
{
  "skill_version": "1.0.0",
  "runtime_status": "ready",
  "platform": "windows-x64",
  "python_mode": "managed",
  "python_version": "3.x",
  "node_mode": "managed",
  "node_version": "xx",
  "powerpoint_version": "detected-version",
  "powerpoint_available": true,
  "powerpoint_com_verified": true,
  "verified": true
}
```

具体 Schema 后续定义。

---

# 11. Fast Preflight

## 11.1 目标

正常任务开始前不重复执行完整 Bootstrap。

只做快速确认：

```text
Managed Runtime 是否存在
依赖 Manifest 是否匹配
Microsoft PowerPoint 与 PowerPoint COM 是否仍可调用
输出目录是否可写
关键能力是否仍存在
```

## 11.2 顺序

Fast Preflight 必须发生在：

```text
Layout Planner
```

之前。

原则：

> Runtime 未 Ready，不得先调用语义 Planner。

## 11.3 Fast Preflight 不做

正常情况下不应每次：

- 重新 `pip install`；
- 重新 `npm install`；
- 重新创建虚拟环境；
- 重新下载 Runtime；
- 重新运行完整 Smoke Test。

---

# 12. Runtime Repair

## 12.1 触发条件

Fast Preflight 发现：

- Python 环境丢失；
- 某个锁定依赖缺失；
- Node modules 损坏；
- Runtime Manifest 与实际状态不一致；
- Backend 路径变化；
- 可修复的环境问题；

则进入 Runtime Repair。

## 12.2 Repair 流程

```text
Fast Preflight Fail
↓
Classify Environment Problem
↓
Repair
↓
Reverify
├─ Pass → Resume Task
└─ Fail → Environment Failure
```

## 12.3 Repair 原则

Repair：

- 不消耗视觉修订次数；
- 不算 Layout Planner semantic revision；
- 不应重新调用 Layout Planner；
- 不应删除已完成的内容规划成果；
- 不应修改用户材料。

## 12.4 典型 Repair

允许：

- 恢复缺失 Python package；
- 恢复缺失 node_modules；
- 重建受控 venv；
- 修复 Runtime Cache；
- 重新探测 Backend；
- 更新 Runtime Manifest。

---

# 13. Environment Failure

## 13.1 定义

当：

```text
Bootstrap / Repair / Verify
```

均无法使 Runtime 达到当前任务所需能力时：

```text
environment_failure
```

## 13.2 行为

Environment Failure 时：

- 不调用 Layout Planner；
- 不调用 Visual Reviewer；
- 不进入 Build；
- 保留用户输入和已完成上游成果；
- 明确报告环境问题；
- 不将其误判为内容问题；
- 不重新生成大纲；
- 不进入无上限重试。

---

# 14. 安全与系统修改边界

## 14.1 不应污染全局环境

默认不应：

- 修改用户全局 Python 包；
- 修改用户全局 Node 包；
- 覆盖系统 Python；
- 强制修改系统 PATH；
- 修改无关系统代理；
- 修改用户 PowerPoint 配置；
- 修改无关 Office 注册表设置。

## 14.2 需要系统级修改时

如确有必要：

- 应明确说明；
- 应最小化修改范围；
- 应支持验证；
- 应避免影响其他应用。

---

# 15. Host Agent 与 Runtime 的职责

## 15.1 Host Agent

Host Agent 负责：

- 发起 Runtime readiness 检查；
- 根据结果决定是否继续；
- 在 Runtime 未 Ready 时调用 Bootstrap / Repair；
- 向用户报告无法自动恢复的问题。

Host Agent 不负责：

- 自己寻找随机 Python 解释器；
- 自己临时 `pip install` 任意包；
- 自己改变 Skill Runtime 规则；
- 环境未 Ready 时先调用 Layout Planner。

## 15.2 Runtime

Runtime 负责：

- Bootstrap；
- Verify；
- Fast Preflight；
- Repair；
- Backend detection；
- Managed dependency state。

---

# 16. 与 Single-Slide Runtime 的交接

任务执行前：

```text
Host
↓
Fast Preflight
├─ Ready
│   ↓
│ Single-Slide Runtime
│   ↓
│ Layout Planner
│
└─ Not Ready
    ↓
  Runtime Repair
    ↓
  Reverify
    ├─ Ready → Single-Slide Runtime
    └─ Fail → environment_failure
```

因此：

> Environment Readiness 是 Single-Slide Runtime 的前置 Gate。

---

# 17. 用户体验要求

第一版应尽可能实现：

```text
安装 Skill
↓
首次自动初始化
↓
验证
↓
之后直接使用
```

普通用户不应被要求：

- 手动判断哪个 Python 环境正确；
- 手动判断缺哪个包；
- 手动切换 venv；
- 手动定位 node_modules；
- 手动判断 PowerPoint COM 是否可用。

只有自动 Bootstrap / Repair 无法完成时，才应要求用户介入。

---

# 18. 第一阶段平台策略

## 18.1 唯一正式平台

第一阶段只正式支持：

```text
Windows
+
Microsoft PowerPoint Desktop
+
PowerPoint COM
```

可由 Claude Code 或 Codex 作为 Host 调用。

## 18.2 非当前范围

以下内容不属于 v2.0 第一阶段安装、执行或 Release Gate：

- macOS；
- Linux；
- LibreOffice；
- Windows without Microsoft PowerPoint；
- 其他 Office / Render Backend。

## 18.3 后续扩展

架构不应无必要地阻止未来增加其他 Backend，但当前不实现、不验收、不发布这些能力。

---

# 19. 验收标准

Runtime Installation & Bootstrap v1.1 至少应满足以下验收条件：

1. Skill 安装后能够建立受控 Runtime；
2. Python 项目依赖不依赖用户全局 site-packages；
3. Node 项目依赖不依赖全局 npm 包；
4. 安装后能够生成 Runtime Manifest；
5. 能够确认当前系统为 Windows；
6. 能够检测 Microsoft PowerPoint Desktop 并验证 PowerPoint COM；
7. 能够执行最小 PPT Smoke Test；
8. 正常任务开始前存在 Fast Preflight；
9. Fast Preflight 必须在 Layout Planner 前完成；
10. Preflight 发现可修复依赖问题时能够进入 Runtime Repair；
11. Repair 成功后能够继续原任务；
12. Repair 不触发新的 Layout Planner semantic call；
13. Repair 不消耗视觉修订次数；
14. 无法恢复时能够明确产生 `environment_failure`；
15. 不出现环境错误导致的无限 Agent 重试；
16. 普通运行不要求用户手工切换多个 Python 环境；
17. Runtime 环境状态与任务 `run_state` 明确分离。

---

# 20. 第一版核心实现组件建议

概念上建议包含：

```text
install.ps1

scripts/
├─ bootstrap_runtime.py
├─ verify_install.py
├─ environment_preflight.py
└─ repair_runtime.py

runtime/
├─ dependency lock files
└─ runtime manifest schema / metadata
```

具体目录和脚本名称可在架构设计阶段调整，本节仅作为实现范围参考，不作为不可变接口。

---

# 21. 最终规范定义

`Content to Editable PPT Skill` 的运行环境安装与引导原则可以概括为：

> Skill 应尽可能在安装或首次运行阶段自动准备、隔离并验证自身所需 Runtime，而不是依赖用户机器上任意的 Python、Node 或项目包状态。正常任务开始前必须执行快速环境预检，只有 Windows、Microsoft PowerPoint Desktop 和 PowerPoint COM 全部验证通过时才能进入 Layout Planner。可修复的依赖或 Manifest 问题应通过 Runtime Repair 自动恢复；无法恢复或系统不在支持范围时，必须明确产生 `environment_failure`，不得转向兼容 Backend。
