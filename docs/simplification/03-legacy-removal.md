# 阶段 3：删除旧体系并缩减安装包

## 文档状态

- 状态：依赖阶段 2
- 前置文档：[阶段 2：建立并原子切换多页主入口](02-single-entry-cutover.md)
- 后续阶段：[阶段 4：核心验证与文档收口](04-core-validation-and-documentation.md)
- 总计划：[Content to Editable PPT Skill 精简计划](../skill-simplification-plan.md)

本阶段只是仓库改造批次，不是 Skill Runtime 阶段或用户状态。

本阶段执行真正的文件精简。只能删除已从多页主入口断开且不属于单页生产保留闭包的功能簇。历史恢复依赖 Git，不创建新的 `archive/`、`legacy-backup/` 或迁移数据库。

## 目标

1. 删除旧 P 阶段的外部入口和不可达内部实现；
2. 合并重复 Schema 和 Reference；
3. 删除只服务 Gate、Evidence、Replay 和历史 Fixture 的代码；
4. 根据阶段 1 决定缩减 Agent 配置；
5. 删除只保护已删除实现的测试和 Fixture；
6. 在正式安装包稳定后，再清理仓库级 Baseline、Report 和阶段工具；
7. 保持多页主入口、独立单页兼容入口、核心编辑性和 PowerPoint 运行能力不回退。

## 前置条件

必须全部满足：

- 阶段 2 的 `scripts/run.py` 多页主入口与 ADR-043 已合入；
- 新 `SKILL.md` 和 README 已生效；
- 一套真实小型多页 Deck 已通过；
- 独立图片转单页兼容入口的完整生产闭包已冻结；
- Agent 单页保留与 Deck-only 拆分边界已冻结；
- 已有生产保留、迁移期保留和删除候选清单；
- 旧入口已从正式 Skill 不可发现。

任何前置条件缺失时，不得批量删除。

## 删除原则

### 1. 按功能簇删除

每个删除提交只处理一个可解释的功能簇，例如：

- 旧内容规划状态机；
- 旧 Markdown Wireframe 管理链；
- 旧 Visual System/Prompt Package 链；
- 旧 Design Preview Evidence 链；
- 旧 Reconstruction State 链；
- 旧 P5 Review/Packaging Evidence 链；
- Deck-only Consistency/Exception Reviewer 与 P5 Evidence 流程；
- 阶段专用测试和 Fixture。

不得一次性删除全部 100 个脚本或 107 个 Schema。

### 2. 删除代码时同步删除引用

同一提交必须同时清理：

- Python/JavaScript import；
- CLI 命令；
- Schema 引用；
- `SKILL.md`、Reference 和 README 链接；
- 测试和 Fixture；
- 安装或依赖检查；
- Agent Prompt 中的文件名；
- 工具脚本中的旧入口。

### 3. 不建立兼容层

如果删除导致多页主入口或独立单页兼容入口失败，应恢复该功能簇并重新研究依赖。不得新增：

- 通用旧 JSON 适配器；
- 双写新旧 Artifact；
- 长期迁移状态；
- 自动识别历史版本的分支树；
- 新归档目录。

## 实施顺序

### 步骤 1：删除旧外部入口

优先处理已从 `SKILL.md`、README 和正式 Agent Prompt 移除的：

- 旧 `manage_*` 外部 CLI；
- P0～P5 专用评估入口；
- 旧 Host Smoke；
- 旧 Replay 命令；
- 旧 Gate 调用示例。

如果多页主入口仍 import 某个 `manage_*` 文件，应先把必要函数迁移到 `scripts/core/` 或等价内部模块，再删除外部 CLI 包装。

### 步骤 2：合并核心 Artifact

以用户概念为中心保留最小数据：

- 用户请求；
- 已确认页面方案；
- 内部构建结果；
- 最终输出。

删除候选包括：

- 同一概念的 Candidate、Approved、State、Manifest、Validation Report 多份变体；
- 只记录阶段迁移的 State；
- 只保存 Canonical Hash 闭包的 Artifact；
- 只服务固定 Evidence 的 Call Record；
- 只服务 Correction Budget 的 Record。

Schema 合并必须保持字段语义清楚，不得为了减少数量制造一个无边界的万能 Schema。

### 步骤 3：缩减 Reference

目标职责：

- 内容与布局；
- PPT 构建；
- 视觉质量；
- 交付。

将仍有效规则迁入上述职责文档后，删除旧阶段 Reference。不得保留多份“增量权威”文件。

### 步骤 4：处理 Agent 配置

依据阶段 1 决定：

- 删除只服务旧 Planner/Reviewer Evidence 的 YAML 和 Prompt；
- 完整保留独立单页入口所需的 Planner、Reviewer 和正常审核交付依赖，并将其限制在该入口；
- 保留 Skill 元数据需要的配置时，删除其中旧 P 阶段描述；
- 不保留 Deck Consistency、Exception Batch 或 Reviewer Ledger，仅因为历史测试仍引用。

### 步骤 5：缩减测试和 Fixture

删除测试前必须确认其保护对象已经删除或被新核心测试替代。

保留测试保护：

- 内容完整和顺序；
- 文字溢出和元素越界；
- 原生文字及主要结构可编辑；
- PowerPoint 打开、保存和渲染；
- 多页主入口不读取非生产目录；
- 独立单页兼容入口及完整审核交付流程。

删除候选：

- 状态迁移矩阵；
- Correction 次数；
- Hash 闭包；
- 固定 D03/D05/D08 Replay；
- 已删除 Schema 的契约测试；
- 阶段 Gate 报告生成测试；
- 历史 Smoke 输出测试。

### 步骤 6：清理仓库历史支撑

正式安装包稳定后，再删除：

- 不再对应当前生产能力的 `baseline/` 文件；
- 阶段 `reports/` 和 Evidence；
- `tools/` 中阶段评估器；
- 已失效的历史 Fixture；
- 旧 P 阶段计划和重复规格。

保留许可证、来源证明和仍被正式运行使用的第三方资料。

## 每个功能簇的验证模板

删除前：

```powershell
rg -n "<module-or-schema-name>" content-to-editable-ppt tests tools docs README.md
git ls-files "*<name>*"
```

删除后：

```powershell
rg -n "<module-or-schema-name>" content-to-editable-ppt tests tools docs README.md
python content-to-editable-ppt/scripts/verify_install.py
git diff --check
```

并执行：

- 与该功能簇相关的核心测试；
- 多页主入口真实小型 Deck；
- 独立单页兼容核心回归；
- PowerPoint 打开或渲染检查。

`rg` 残留必须逐条解释，不能因为它位于文档中就自动忽略。

## 变更记录要求

每个删除提交只在提交或 PR 说明中记录：

- 删除的文件和入口数量；
- 替代它们的新入口或核心模块；
- 保留的用户能力；
- 执行的验证；
- 如有暂缓删除，说明真实依赖。

不新增永久 Deletion Manifest 或迁移数据库。

## 验收清单

- [ ] 所有删除基于阶段 1 引用清点；
- [ ] 多页主入口保持可用；
- [ ] 独立单页兼容入口及完整审核交付流程保持可用；
- [ ] 安装依赖和锁文件完整；
- [ ] PPT、字体、渲染、图片和 SVG 核心模块未误删；
- [ ] 旧外部入口已删除；
- [ ] 只服务阶段 State、Gate、Evidence 和 Replay 的模块已删除；
- [ ] Schema 和 Reference 已按用户概念收敛；
- [ ] Agent 配置符合阶段 1 决定；
- [ ] 只保护已删除实现的测试和 Fixture 已清理；
- [ ] 没有新兼容层或归档目录；
- [ ] 真实小型 Deck 持续通过；
- [ ] 正式安装包实现净文件减少；
- [ ] `git diff --check` 通过。

## 完成标准

正式安装包中的每个文件都能对应：

- 当前用户能力；
- 核心质量或安全风险；
- 必要运行依赖；
- 法律和来源要求。

不存在仅因历史 P 阶段、Gate、Evidence 或 Fixture 而保留的正式安装文件。

## 回退

按功能簇回退。恢复失败功能簇后重新执行多页主入口和单页兼容验证。不得整体恢复 P0～P5，也不得用长期适配器代替正确依赖分析。

## 交接到阶段 4

交接时提供：

- 精简后正式安装包文件统计；
- 多页主入口及内部核心模块列表；
- 独立单页兼容入口生产保留闭包；
- 最终保留 Schema、Reference 和 Agent 配置；
- 最终核心测试候选；
- 已删除历史工具和资料范围；
- 真实小型 Deck 的当前验证命令和结果。
