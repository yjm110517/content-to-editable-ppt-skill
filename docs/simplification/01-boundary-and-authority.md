# 阶段 1：边界清点与权威切换

## 文档状态

- 状态：待实施
- 前置条件：无
- 后续阶段：[阶段 2：建立并原子切换唯一入口](02-single-entry-cutover.md)
- 总计划：[Content to Editable PPT Skill 精简计划](../skill-simplification-plan.md)

本阶段只是仓库改造批次，不是 Skill Runtime 阶段或用户状态。

本阶段对运行代码只读，只修改决策和权威文档。不得删除生产脚本、Schema、Reference、Agent 配置或测试，不得提前改写当前生效的 `SKILL.md`。

## 目标

1. 确认正式 Skill 当前真正使用的能力和依赖；
2. 将正式安装包文件分为生产保留、迁移期保留、删除候选、无引用四类；
3. 决定图片转单页兼容入口是否继续存在；
4. 决定 Planner、Reviewer 配置在精简后是否仍有真实用途；
5. 通过 ADR 正式终止继续扩展 P0～P5 的方向；
6. 为阶段 2 提供明确的唯一入口边界。

## 当前基线

开始实施时必须重新统计，不能只引用总计划中的旧快照。当前已知基线为：

| 区域 | 文件数 |
|---|---:|
| 正式安装包 | 234 |
| `scripts/` | 100 |
| `schemas/` | 107 |
| `references/` | 14 |
| `agents/` | 6 |
| `tests/` | 119 |
| `baseline/` | 283 |
| `reports/` | 40 |
| `tools/` | 18 |

当前权威来源包括 README 中声明的 Architecture v2.4、ADR、Specification v1.6、Contract v1.4 和 Testing v1.4。精简计划不能仅靠修改自身状态取代这些来源。

## 工作范围

### 包含

- 正式安装包文件引用清点；
- 外部命令入口清点；
- Schema、Reference 和 Agent 配置使用情况；
- 生产代码对 `tests/`、`baseline/`、`reports/`、`tools/` 和 `work/` 的引用；
- 图片转单页兼容入口的真实使用判断；
- ADR 和 README 权威层级调整。

### 不包含

- 新建统一入口；
- 删除旧命令或旧 Schema；
- 合并测试；
- 修改 PPT 构建和视觉布局；
- 修复本次截图中的图文重叠；
- 新建长期清单、数据库或归档目录。

## 清点方法

### 1. 重新确认工作树

```powershell
git status --short --branch
git diff --check
git ls-files content-to-editable-ppt
```

保留用户已有修改，不将无关工作树变化纳入本阶段。

### 2. 统计正式安装包组成

```powershell
git ls-files content-to-editable-ppt/scripts
git ls-files content-to-editable-ppt/schemas
git ls-files content-to-editable-ppt/references
git ls-files content-to-editable-ppt/agents
```

统计结果写入本阶段的提交或 PR 说明，不创建永久 `inventory.json`。

### 3. 清点外部入口

重点检查：

- `install.ps1`；
- `SKILL.md` 中出现的命令；
- `manage_*.py`；
- `run_pipeline.py`；
- `tools/**/*eval*.py`；
- Agent Prompt 中要求执行的脚本；
- README 和当前规格中公开的命令。

使用 `rg` 查找所有入口引用：

```powershell
rg -n "manage_|run_pipeline|p[0-5].*eval|prepare_agent_call|finalize_agent_response" README.md content-to-editable-ppt docs tests tools
```

### 4. 建立引用关系

对每个正式安装文件回答：

1. 是否由正式 `SKILL.md` 直接引用；
2. 是否由生产脚本 import 或调用；
3. 是否只由测试、Fixture 或阶段评估器引用；
4. 是否只为历史 Evidence 服务；
5. 删除后会影响哪项用户能力；
6. 是否属于必要依赖或许可证文件。

分类规则：

| 分类 | 判断标准 | 后续处理 |
|---|---|---|
| 生产保留 | 当前用户能力或核心风险直接依赖 | 阶段 2/3 保留或迁移 |
| 迁移期保留 | 新入口切换前仍被旧入口调用 | 阶段 2 验证后删除 |
| 删除候选 | 只服务旧 P 阶段、Gate、Evidence 或 Fixture | 阶段 3 删除 |
| 无引用 | 无生产、测试或文档引用 | 核实后阶段 3 删除 |

清点结果放在阶段提交或 PR 描述中。完成删除后不保留新的长期清单文件。

### 5. 审计 Agent 配置

分别判断：

- `planner.yaml` 和 Planner Prompt 是否只服务图片转单页布局；
- `visual_reviewer.yaml` 是否只服务旧 Reviewer Evidence 和 P5 Gate；
- `openai.yaml` 是否仍是安装 Skill 所需元数据；
- Host 是否可以直接承担内容和页面方案工作；
- 删除 Reviewer 后，现有确定性检查能否覆盖必要的文件和编辑性风险。

输出必须形成明确决定，不能保留“以后再看”的默认状态。

### 6. 决定兼容入口

图片转单页可编辑 PPT 只能选择一种结果：

- 保留：存在真实使用证据，并通过统一入口的独立模式访问；
- 删除：没有真实使用证据，相关 Planner、Schema、脚本和测试进入阶段 3 删除候选。

不得因历史实现已经存在而默认保留。

“真实使用证据”至少应满足一项：

- 用户曾明确请求该入口对应的能力；
- 存在测试和 Baseline 之外的当前任务调用记录；
- 存在明确的外部消费者或当前产品承诺。

代码已经存在、历史 Fixture、Baseline、阶段 Report 和旧开发计划本身不构成真实使用证据。

## 权威切换

### ADR 内容

在 [DECISIONS.md](../../DECISIONS.md) 中新增下一个可用 ADR，至少记录：

- 决策背景：P0～P5 工程验证体系造成用户流程和安装包膨胀；
- 决策：用户侧改为提供材料、确认方案、接收结果；
- 正式 Skill 只保留一个生产入口；
- 阶段 Gate、Evidence、Fixture Replay 和 Field Validation 不再是产品能力；
- 历史文档只用于追溯；
- 本精简计划及四份实施文档成为后续执行依据；
- 在阶段 2 原子切换前，旧 `SKILL.md` 仍保持可执行。

### README 调整

只调整权威层级和后续开发方向，不在本阶段提前公布尚不存在的新入口。

README 必须明确：

- 当前运行路径在阶段 2 切换前仍有效；
- 后续开发停止扩展 P0～P5；
- 精简计划是迁移依据；
- 用户流程最终将收敛为单一路径。

## 阶段输出

本阶段只产生：

1. 一个 ADR；
2. README 权威层级调整；
3. 提交或 PR 描述中的一次性引用清点；
4. 图片转单页入口保留/删除决定；
5. Agent 配置保留/删除决定；
6. 阶段 2 的唯一入口最小输入输出契约。

不得新增长期 Inventory、State、Manifest、Gate Report 或 Evidence 文件。

ADR 或阶段交接必须记录承载清点结果的具体提交 SHA 或 PR 编号，保证后续执行者可以冷启动定位；无需把清点复制成新的永久文件。

## 验证清单

- [ ] 重新统计文件数量；
- [ ] 每个正式安装文件都有分类；
- [ ] 所有公开命令入口已识别；
- [ ] 生产代码对测试和历史目录的引用已识别；
- [ ] 图片转单页入口已有明确决定；
- [ ] Planner、Reviewer 和 `openai.yaml` 已分别决定；
- [ ] ADR 已采用下一个有效编号；
- [ ] README 与 ADR 不矛盾；
- [ ] 当前 `SKILL.md` 和生产入口未被提前切换；
- [ ] 没有删除运行代码；
- [ ] `git diff --check` 通过。

## 阶段完成标准

阶段 2 的执行者无需重新研究旧 P 阶段历史，即可从 ADR、总计划和本阶段提交说明中获得：

- 要保留的用户能力；
- 唯一入口的最小契约；
- 兼容入口决定；
- Agent 角色决定；
- 旧文件的删除边界。

## 回退

本阶段不删除代码。若 ADR 或边界决定存在问题，只修订 ADR 和 README。不得通过新增兼容层解决尚未确认的需求。

## 交接到阶段 2

交接时提供：

- ADR 编号和链接；
- 唯一入口最小输入输出契约；
- 兼容入口决定；
- Agent 配置决定；
- 生产保留与迁移期保留文件列表；
- 删除候选列表；
- 已核实并入删除候选的无引用文件列表；
- 禁止阶段 2 调用的测试和历史目录列表。
