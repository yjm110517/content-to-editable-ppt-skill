# 阶段 2：建立并原子切换多页主入口

## 文档状态

- 状态：依赖阶段 1
- 前置文档：[阶段 1：边界清点与权威切换](01-boundary-and-authority.md)
- 后续阶段：[阶段 3：删除旧体系并缩减安装包](03-legacy-removal.md)
- 总计划：[Content to Editable PPT Skill 精简计划](../skill-simplification-plan.md)

本阶段只是仓库改造批次，不是 Skill Runtime 阶段或用户状态。

本阶段先在旧多页实现后建立一个最小主入口，完成真实 Deck 验证后，再在同一切换提交中启用新多页入口并重写 `SKILL.md`、README。独立 `run_pipeline.py` 单页兼容入口及其完整审核交付流程保持不变。

## 目标

1. 建立唯一可发现的多页 Content-to-Deck 主入口；
2. 入口只接收用户请求、材料、确认后的页面方案和输出位置；
3. 隐藏内部规划、构建、校验和交付函数；
4. 使用现有可靠底层模块完成真实多页 PPT；
5. 原子切换正式 `SKILL.md` 和 README；
6. 使测试、Smoke、Fixture 和阶段评估器无法从多页主入口到达；
7. 保证独立单页兼容入口及完整依赖闭包不回退。

## 前置输入

必须从阶段 1 获得：

- 已合入的精简 ADR；
- 独立单页入口生产保留闭包；
- Agent 单页保留与 Deck-only 拆分边界；
- 多页主入口最小输入输出契约；
- 生产保留和迁移期保留文件列表；
- 删除候选和已核实无引用文件列表；
- 禁止读取的开发和历史目录列表。

缺少任一决定时不得自行扩大兼容范围。

## 多页主入口边界

### 用户和宿主看到的流程

```text
用户提供材料
→ 宿主展示一次合并方案
→ 用户确认
→ 宿主调用多页主入口
→ 返回 PPTX 和预览
```

### 外部入口

建议使用 `scripts/run.py`，实际名称可在阶段 1 决定。它是唯一多页主入口，不提供用户必须理解的 `plan/build/verify/deliver` 子命令。现有 `scripts/run_pipeline.py` 继续作为独立单页兼容入口。

入口最少接收：

- 一个用户侧 Request 包，其中包含原始用户要求、材料引用和用户已确认的页面方案；
- 工作目录；
- 输出目录；
- 必要的 Python、Node 和 PowerPoint 运行配置。

确认后的页面方案是用户侧 Request 的一部分，不建立独立 Candidate、Approved、State 或 Authority Artifact。

入口只返回：

- 成功或失败；
- 最终 PPTX 路径；
- 预览路径；
- 简明错误信息。

内部 Build Report 可以存在，但不能成为用户需要读取或确认的步骤。

### 禁止输入

多页主入口不得接受：

- 旧 Candidate、State、Manifest 或 Gate Report；
- Baseline Case；
- 测试 Fixture；
- Smoke Record；
- D03、D05、D08 Evidence；
- P 阶段 Report；
- Reviewer Evidence Package。

通过输入类型和入口目录隔离实现，不新增针对文件名字符串的哨兵体系。

## 实施步骤

### 1. 建立薄入口

新增一个薄入口，只负责：

- 规范化路径；
- 校验最小输入；
- 调用内部构建流程；
- 收集最终输出；
- 返回单一机器可读结果；
- 将诊断写入日志或标准错误。

不得在入口中重新实现 PPT Builder、字体渲染或资产处理。

### 2. 复用底层能力

优先复用阶段 1 判定为生产保留的模块：

- PPT 原生文字、形状、线条、图片和图表构建；
- 字体解析和审计；
- PowerPoint 渲染；
- SVG 和图片资产处理；
- 内容完整性、溢出、越界、可编辑性和文件打开检查。

旧 `manage_*` 文件可以暂时作为内部实现被调用，但不能从新 `SKILL.md` 暴露。

### 3. 处理用户确认

用户确认由宿主 Agent 完成。生产入口只消费已经确认的页面方案，不在 CLI 内建立等待用户输入的状态机。

确认方案只包含用户能理解的信息：

- 页面顺序；
- 每页标题和核心内容；
- 基本布局；
- 视觉方向。

不得要求用户确认 Hash、Manifest、Authority 或 Reconstruction Seed。

### 4. 保护独立单页入口

- `run_pipeline.py` 继续独立访问，不并入新的多页主入口；
- Planner Initial/Revision、Visual Reviewer 单页 Review、`run_state`、Recovery、Patch、Review Gate、Warning Acceptance、Delivery Decision 和七文件交付保持有效；
- 单页状态和 Reviewer 不进入新的多页主路径；
- `visual_reviewer.yaml` 的 Deck-only Profile 可以拆分，但单页 Review Profile 及依赖不得删除；
- 现有单页核心回归必须通过。

### 5. 完成真实 Deck 验证

在切换文档前，使用一套小型真实多页材料验证：

- 至少 3 页；
- 包含标题、正文、简单结构或图表；
- 输出原生可编辑文字；
- PPTX 可由 PowerPoint 打开；
- 可以生成预览；
- 不读取测试或历史目录。

该 Deck 只是迁移验证，不建立新的长期 Field Validation 体系。

### 6. 原子切换

在一个不可拆分的提交中完成：

1. 启用唯一多页主入口；
2. 重写 `content-to-editable-ppt/SKILL.md`；
3. 更新 README 的用户流程、安装和调用说明；
4. 移除 `SKILL.md` 中全部 P1～P5、D03/D05/D08、Smoke、Replay、Gate 和 Evidence 调度；
5. 将旧入口从正式文档和 Agent 可发现路径移除；
6. 保留旧内部实现供阶段 3 删除，不对用户公开。

## `SKILL.md` 目标结构

新 `SKILL.md` 只需要说明：

1. 适用任务；
2. 可接受材料；
3. 如何形成和展示一次合并方案；
4. 用户确认后如何调用多页主入口，以及何时使用独立单页兼容入口；
5. 核心可编辑性和图文边界；
6. 失败时何时停止；
7. 多页主路径默认交付 PPTX 和预览；独立单页入口继续现有七文件交付。

不包含开发状态、里程碑、Fixture、Gate 命令或历史 ADR 细节。

## 验证命令

实际命令应在入口确定后补充，至少执行：

```powershell
python content-to-editable-ppt/scripts/run.py --help
python content-to-editable-ppt/scripts/verify_install.py
git diff --check
```

此外必须执行真实小型 Deck 的端到端命令，并检查：

- 返回码；
- PPTX 存在；
- 预览存在；
- PowerPoint 打开成功；
- 原生文字对象存在；
- 日志未读取禁止目录。

## 验收清单

- [ ] 唯一多页主入口已建立；
- [ ] 入口没有用户级子阶段；
- [ ] 宿主负责一次确认，CLI 不维护等待状态；
- [ ] 真实小型多页 Deck 通过；
- [ ] 生产入口不读取测试、Smoke、Baseline 或 Report；
- [ ] 独立单页兼容入口及完整审核交付流程保持有效；
- [ ] `SKILL.md` 和 README 在同一提交切换；
- [ ] `SKILL.md` 不再出现 P1～P5 调度；
- [ ] 旧入口从正式文档不可发现；
- [ ] 旧内部模块尚未提前批量删除；
- [ ] 没有通用旧 Artifact 兼容层；
- [ ] `git diff --check` 通过。

## 阶段输出

- 唯一多页主入口；
- 精简后的 `SKILL.md`；
- 更新后的 README；
- 一套通过的真实小型 Deck 验证结果；
- 阶段 3 可以删除的旧入口和迁移模块列表，记录在提交或 PR 描述中。

不新增阶段 State、Cutover Manifest、Gate Report 或 Evidence Package。

## 完成标准

新用户只通过 `SKILL.md` 能理解：多页任务提供材料、确认方案并得到 PPTX；参考图片单页重建继续使用独立兼容入口。宿主只发现一个多页主入口和一个独立单页兼容入口。

## 回退

切换必须整体回退：入口、`SKILL.md` 和 README 一起恢复。不得只恢复一部分，也不得用额外兼容层修补半完成切换。

## 交接到阶段 3

交接时提供：

- 多页主入口路径和稳定输入输出；
- 独立单页兼容入口生产保留闭包；
- 真实 Deck 验证命令；
- 仍由多页主入口调用的底层模块；
- 已从正式路径断开的旧入口；
- 可删除的 Schema、Reference、Agent 配置和测试簇。
