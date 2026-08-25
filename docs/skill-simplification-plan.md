# Content to Editable PPT Skill 精简计划

## 1. 文档定位

- 状态：待批准的执行计划
- 目标：先缩减正式 Skill，再在精简后的单一路径上处理视觉质量问题
- 适用范围：`content-to-editable-ppt/` 正式安装包，以及与其直接耦合的测试、工具和文档
- 不扩展范围：不新增用户入口、输入格式、Agent 角色、阶段、状态机、Gate 或 Evidence 体系

当前 README 仍将 Architecture v2.4、ADR、Specification v1.6、Contract v1.4 和 Testing v1.4 列为权威来源。因此，本计划在获得批准后，必须先通过新的 ADR 正式终止“继续扩展 P0～P5”的方向，并同步 README 的权威层级。在该 ADR 合入之前，本文档只是一份待批准计划，不自行取代现有权威文件。

本计划是后续精简工作的唯一总计划。根据用户要求，仅建立下列四份配套实施文档；不得继续扩展第五份阶段文档、精简状态机或证据体系。

### 配套实施文档

| 顺序 | 实施文档 | 状态 |
|---:|---|---|
| 1 | [边界清点与权威切换](simplification/01-boundary-and-authority.md) | 待实施 |
| 2 | [建立并原子切换唯一入口](simplification/02-single-entry-cutover.md) | 依赖阶段 1 |
| 3 | [删除旧体系并缩减安装包](simplification/03-legacy-removal.md) | 依赖阶段 2 |
| 4 | [核心验证与文档收口](simplification/04-core-validation-and-documentation.md) | 依赖阶段 3 |

## 2. 当前问题

当前仓库混合了四类职责：

1. 面向用户的内容转可编辑 PPT Skill；
2. 图片转单页可编辑 PPT 的历史 Runtime；
3. P0～P5 工程验证框架；
4. Baseline、Fixture、Replay、Live Evidence 和 Field Validation 资料。

主要规模基线如下：

| 区域 | 受版本控制文件数 | 说明 |
|---|---:|---|
| 正式安装包合计 | 234 | 包含运行文件及大量阶段契约 |
| `content-to-editable-ppt/scripts/` | 100 | 命令入口、状态机和底层模块混合 |
| `content-to-editable-ppt/schemas/` | 107 | 大量中间 Artifact 各自拥有 Schema |
| `content-to-editable-ppt/references/` | 14 | 交叉引用较多 |
| `content-to-editable-ppt/agents/` | 6 | Planner、Reviewer 配置与 Prompt |
| `tests/` | 119 | 核心回归和阶段 Gate 测试混合 |
| `baseline/` | 283 | 历史冻结结果 |
| `reports/` | 40 | 阶段验收及 Evidence |
| `tools/` | 18 | Baseline 和 P 阶段评估入口 |

当前 [SKILL.md](../content-to-editable-ppt/SKILL.md) 直接要求宿主理解和调度 P1、P2、P3.1、P3.2、P3.3、P4 和 P5，同时暴露 Candidate、Authority、Prompt Package、Reconstruction Seed、Live Review Evidence、Packaging Runtime Lock 等内部概念。

用户真正关心的是：

```text
提供材料
→ 确认方案
→ 得到可编辑 PPT
```

本次出现的 `WORKFLOW SMOKE ONLY` 图文混乱结果也说明：开发测试路径和用户路径未彻底分开。临时 Smoke 脚本能够生成类似正式预览的 Contact Sheet，而被质量检查拒绝的图片仍能出现在非生产预览中。

## 3. 精简后的产品定义

精简后的 Skill 定义为：

> 用户提供主题、文档、大纲或参考图片，Skill 形成简明页面方案；用户确认后，Skill 生成结构清楚、文字和主要结构可编辑的 PowerPoint，并交付最终 PPTX 和预览。

用户侧只有三个动作：

1. 提供材料和要求；
2. 确认内容、页面结构和视觉方向；
3. 接收预览和最终 PPTX。

用户或宿主 Agent 不需要分别调度 `plan`、`build`、`verify`、`deliver`。即使代码内部存在同名函数，它们也只是统一入口内部实现，不得发展为四套状态、Schema、Gate、恢复流程或用户阶段。

产品成功标准是：

- 内容符合用户材料；
- 页面顺序和信息层级清楚；
- 不存在阻断阅读的图文重叠、文字溢出或元素越界；
- 标题、正文、卡片、线条、箭头和简单图表保持原生可编辑；
- PPTX 能在 Microsoft PowerPoint 中正常打开和保存；
- 用户能够明确区分方案、预览和最终文件。

## 4. 范围边界

### 4.1 第一目标：缩减正式 Skill

第一目标完成以下事项：

- 用户侧取消 P0～P5；
- 正式 Skill 只保留一个生产入口；
- 删除安装包中的阶段调度、阶段 Gate、阶段 Evidence 和仅服务历史 Fixture 的代码；
- 合并重复的 Schema、Reference 和命令入口；
- Smoke、Fixture、Baseline、Report 和 Field Validation 从正式路径不可达；
- 核心运行能力和依赖锁文件保持完整。

第一目标不要求同时完成完整视觉布局重构。只需要保证非生产输出不能再被正式入口展示。

### 4.2 第二目标：在精简路径上修复视觉质量

正式 Skill 瘦身完成后，再处理：

- 图片和文字安全区冲突；
- 全页生成视觉与原生文字叠加；
- 图片模型生成重复数字、标签或公式；
- 页面布局未真正使用已确认结构的问题。

第二目标使用精简后的 Request 和 Deck Plan，不得恢复旧 P3.2、P3.3、P4 阶段体系。

### 4.3 明确不扩展的能力

本轮不新增：

- 现有 PPT 作为新的内容输入类型；
- PDF 作为强制默认预览格式；
- 新 Planner、Reviewer 或 QA Agent；
- 新的在线服务或数据库；
- 新的发布平台、前端或后端；
- 新的通用旧 Artifact 兼容层。

内容输入继续以当前已支持的主题、材料、文档、大纲为主。参考图片只用于当前已有的图片重建能力是否保留的评估，不借精简扩大产品范围。

## 5. 必须保留的能力和文件

### 5.1 用户能力

- 内容到多页可编辑 PPT；
- 必要的内容和页面方案确认；
- 原生标题和正文；
- 原生卡片、线条、箭头和简单图表；
- 必要的图片、SVG 和复杂视觉资产；
- Microsoft PowerPoint 构建或渲染验证；
- 基础内容完整性、溢出、越界、图文冲突和可编辑性检查；
- 最终 PPTX 和预览交付。

### 5.2 运行依赖

以下文件属于必要运行基础，不能因为目标目录树简化而误删：

- `scripts/requirements.txt`；
- `scripts/package.json`；
- `scripts/pnpm-lock.yaml`；
- `runtime/vendor-lock.json`；
- `third_party/` 中实际使用资产的许可证和来源；
- `install.ps1`、`LICENSE` 和 `NOTICE`；
- 仍被正式构建使用的共享 PPT、渲染、字体、图片、SVG 和校验模块。

### 5.3 Agent 角色决策

正式内容转 PPT 主路径默认由宿主 Agent 完成内容理解和页面方案，不再要求持久化的独立 Planner、Reviewer Evidence 流程。

对 `agents/` 的处理必须先完成使用审计：

- 如果某个角色只服务旧 P 阶段、独立 Evidence 或历史 Fixture，则从安装包删除；
- 如果图片转单页兼容入口仍有真实用户需求，且确实依赖 Layout Planner，则只为该独立兼容入口保留最小角色配置；
- 不得为了保留 Agent 配置而继续保留旧状态机、Reviewer Gate 或调用证据包。

## 6. 目标结构

目标安装包应接近以下结构：

```text
content-to-editable-ppt/
├─ SKILL.md
├─ references/
│  ├─ content-and-layout.md
│  ├─ ppt-building.md
│  ├─ visual-quality.md
│  └─ delivery.md
├─ schemas/
│  └─ 仅保留用户请求、页面方案、构建结果和交付所需 Schema
├─ scripts/
│  ├─ run.py                 # 唯一外部生产入口
│  ├─ core/                  # 内部规划、构建、校验和交付模块
│  ├─ shared/                # PPT、字体、渲染和资产共享模块
│  ├─ requirements.txt
│  ├─ package.json
│  └─ pnpm-lock.yaml
├─ agents/                   # 仅在保留兼容入口确有需要时存在
├─ runtime/
│  └─ vendor-lock.json
├─ third_party/
├─ install.ps1
├─ LICENSE
└─ NOTICE
```

该目录树表达职责，不强制机械改名。底层已验证模块可以继续存在，但用户和宿主 Agent 只能发现一个生产入口。

默认交付只包含：

```text
<name>_editable.pptx
<name>_preview.png 或 Contact Sheet
```

基础质量结论直接在最终回复中说明。只有运行时确有机器消费需求时才保留内部 Build Report；不得为了形式完整强制新增用户可见 `quality-summary.json`。

## 7. 精简原则

### 7.1 生产入口只接受用户输入

新入口只接受一个用户侧 Request 包和必要运行配置。该 Request 包包含原始用户要求、材料引用以及用户已确认的页面方案；它不是旧 Candidate、State、Manifest 或 Authority Artifact。入口不接受 Gate Report、Smoke Record、Fixture 等内部 Artifact。

因此无需继续增加针对 `SMOKE ONLY`、`rejected` 等字符串的哨兵判断。Smoke 和 Fixture 应从类型、目录和入口上不可达。

### 7.2 不建立长期兼容层

仓库目前没有已确认的外部 API 消费者。除非清点发现真实消费者，否则：

- 不建立通用旧 Artifact 兼容层；
- 必要的一次性迁移脚本必须在同一工作流中删除；
- 历史实现依赖 Git 历史恢复，不新建仓库内 `archive/` 目录；
- 不为 D03、D05、D08 或旧 Fixture 保留生产兼容。

### 7.3 每个文件必须说明用户价值

正式安装包中的每个文件必须至少满足一项：

- 实现当前用户能力；
- 保护内容完整、版面可读、PPT 可编辑或文件可打开等核心风险；
- 提供必要依赖、许可证或安装信息。

仅被历史测试、旧 Gate 或旧 Evidence 引用的文件不进入正式安装包。

### 7.4 数量只作观察指标

脚本、Schema、Reference 和测试数量用于观察精简效果，不作为机械通过门槛。

不得为了达到某个数字：

- 把无关逻辑塞进一个超大文件；
- 删除仍能捕获真实用户风险的测试；
- 合并语义完全不同的 Schema；
- 牺牲可编辑性、内容正确性或文件完整性。

每次变更必须实现净减少，或者明确替代了更多旧文件和入口。

## 8. 执行工作流

整个精简只使用四个串行工作流。它们是代码改造顺序，不是新的用户阶段。

### 工作流一：[边界清点与权威切换](simplification/01-boundary-and-authority.md)

#### 目的

确认保留、删除和暂时依赖的内容，并正式终止继续扩展 P0～P5 的方向。

#### 具体工作

1. 对正式安装包 234 个文件执行引用清点；
2. 将每个脚本、Schema、Reference 和 Agent 配置归为：
   - 当前生产必需；
   - 仅迁移期间需要；
   - 仅历史测试或 Evidence 使用；
   - 无引用；
3. 判断图片转单页兼容入口是否有真实用户需求；
4. 新增 ADR，明确：
   - 用户侧废止 P0～P5；
   - 正式 Skill 改为一个入口；
   - 阶段 Gate、Evidence 和历史 Fixture 不再构成产品能力；
5. 同步 README 的权威层级，使本文档和新 ADR 成为精简依据；
6. 清点结果记录在实施提交或 PR 描述中，不新增永久管理 Artifact。

#### 验证

- 每个正式安装文件都能找到生产引用或删除理由；
- 没有尚未调查便计划删除的运行依赖；
- README、ADR 和本文档对精简方向无冲突；
- 尚未修改当前生效的 `SKILL.md` 或生产入口。

#### 完成标准

后续工作可以根据引用清点安全判断哪些旧文件可删除。

#### 回退

该工作流只改变决策与文档权威，不删除运行代码；如边界判断错误，修订 ADR 和清点结论。

### 工作流二：[建立并原子切换唯一入口](simplification/02-single-entry-cutover.md)

#### 目的

先在旧入口后建立最小新入口，验证成功后，在同一个切换提交中更新 `SKILL.md`、README 并启用新入口，避免文档与代码暂时不一致。

#### 具体工作

1. 建立单一外部入口 `run.py` 或等价入口；
2. 外部入口只接收原始用户请求、材料、输出目录和必要运行配置；
3. 内部可以调用内容规划、构建、验证和交付函数，但不暴露为用户步骤；
4. 使用现有底层模块完成一套真实小型多页 Deck；
5. 如果图片转单页兼容入口决定保留，通过同一入口的明确模式访问，不与多页路径交织；
6. 不建立通用旧 Artifact 适配层；确需一次性迁移代码时，限定在本工作流并在切换完成时删除；
7. 在一次原子切换中：
   - 启用新入口；
   - 重写 `SKILL.md`；
   - 更新 README 的用户流程和命令；
   - 将旧外部入口标记为内部待删除实现；
8. 新 `SKILL.md` 只描述“提供材料、确认方案、接收结果”。

#### 验证

- 新入口能从原始材料生成可打开的多页 PPTX；
- 正常运行不读取 `tests/`、`baseline/`、`reports/`、`tools/*eval*` 或 `work/field-validation/`；
- `SKILL.md` 不包含 P1～P5、D03/D05/D08、Smoke、Replay、Gate 或 Evidence 调度；
- 用户不需要理解或调用内部规划、构建、验证和交付函数；
- 旧入口仍在当前提交内可用于回退，但已不可从正式 Skill 发现。

#### 完成标准

正式 Skill 只有一个可发现入口，且文档和代码在同一提交完成切换。

#### 回退

若新入口失败，整体撤回切换提交；不得只恢复旧 `SKILL.md` 而保留半完成的新入口。

### 工作流三：[删除旧体系并缩减安装包](simplification/03-legacy-removal.md)

#### 目的

根据工作流一的引用清点，删除不再可达的阶段脚本、Schema、Reference、Agent 配置和生产包内防御性工程。

#### 具体工作

1. 先删除旧 P 阶段的外部命令入口；
2. 删除只服务旧状态机、Correction Budget、Evidence Finalizer、Fixture Replay 和阶段 Gate 的模块；
3. 合并表达同一用户概念的 Request、Plan、Build Result 和 Delivery Schema；
4. 合并交叉重复的 Reference；
5. 保留 PPT 构建、字体、渲染、图片、SVG、结构检查和必要安装模块；
6. 根据 Agent 使用审计删除不再需要的 Planner、Reviewer 配置及 Prompt；
7. 删除只保护已删除实现的测试和 Fixture；
8. 正式安装包瘦身完成后，再处理仓库级历史资料：
   - 删除不再对应当前产品的 Baseline、Report 和 Evidence；
   - 删除阶段专用评估工具；
   - 依赖 Git 历史恢复，不创建新归档目录；
9. 每删除一组文件，同时清理 import、文档链接、命令示例和安装引用。

#### 验证

- 安装包内每个文件都对应当前用户能力、核心风险或必要依赖；
- `rg` 和运行时追踪均不存在孤立 import、失效 Schema 引用或旧命令；
- 新入口仍能完成真实小型多页 Deck；
- 保留兼容入口时，其最小 Fixture 通过；
- 正常安装不包含 Baseline、阶段 Report、Smoke 或固定 Evidence；
- 本工作流实现文件、入口和长期 Artifact 的净减少。

#### 完成标准

正式安装包不再包含仅服务 P 阶段、历史 Gate、Replay 或 Evidence 的文件。

#### 回退

按功能簇删除并提交。某个功能簇回归失败时，只恢复该功能簇；不得新建长期兼容层来掩盖引用错误。

### 工作流四：[核心验证与文档收口](simplification/04-core-validation-and-documentation.md)

#### 目的

证明精简后的 Skill 仍能完成用户任务，并清除旧权威文档造成的混淆。

#### 具体工作

1. 保留能够捕获以下风险的最小测试集：
   - 内容丢失或顺序错误；
   - 文字溢出和元素越界；
   - 标题、正文和主要结构不可编辑；
   - PPTX 无法打开、保存或重新渲染；
   - 非生产目录被正式入口读取；
2. 使用一套真实小型多页 Deck 完成端到端验证；
3. 对每个决定保留的兼容入口保留一套最小 Fixture；
4. 测试输出只写临时目录；
5. 记录核心测试耗时，并设置适合本地持续运行的耗时预算；
6. 重写 README，只保留当前产品、安装、输入、确认、生成和交付；
7. 将旧 P0～P5 Architecture、Specification、Contract、Testing 和 Plan 标记为历史，不再逐版本升级；
8. 记录精简前后的安装包文件数、外部入口数、长期 Artifact 数和测试耗时。

#### 验证

- 新用户只读 README 和 `SKILL.md` 即可完成任务；
- 文档中不存在需要用户执行的 P 阶段命令；
- 正式路径不会展示 Smoke、Fixture、Rejected Preview 或 Field Validation 结果；
- 真实小型多页 Deck 内容完整、可打开且主要内容可编辑；
- 核心测试能够捕获内容丢失、溢出、越界、不可编辑、损坏文件和非生产路径误用；
- 精简期间不降低当前已有的质量保护；
- 精简前后对比显示正式安装包、入口和长期 Artifact 均净减少。

#### 完成标准

项目能够直接回答：用户提供什么、在哪里确认、最终 PPTX 在哪里。

#### 回退

运行时问题回退对应功能簇；文档问题独立修订。不得恢复旧 P 阶段作为默认用户流程。

## 9. 执行顺序

四个工作流严格串行：

```text
边界清点与权威切换
→ 建立并原子切换唯一入口
→ 删除旧体系并缩减安装包
→ 核心验证与文档收口
```

不进行并行改造，避免多个工作流同时修改 Request、Deck Plan、Build Result 或 `SKILL.md`。

禁止提前执行：

- 在完成引用清点前批量删除脚本或 Schema；
- 在新入口端到端通过前改写当前生效的 `SKILL.md`；
- 在文档和入口可以原子切换前隐藏旧入口；
- 在新入口稳定前删除迁移保护测试；
- 将旧文件移动到新的长期归档目录；
- 为过渡期再建立一套永久状态、Schema 或 Evidence。

## 10. 精简完成标准

第一目标“正式 Skill 瘦身”完成需要同时满足：

- [ ] README 和 `SKILL.md` 只描述一条用户主路径；
- [ ] 用户侧不出现 P0～P5；
- [ ] 用户只需提供材料、确认方案、接收结果；
- [ ] 正式 Skill 只有一个外部生产入口；
- [ ] 正式入口只接受原始用户输入，不消费内部 Artifact；
- [ ] Smoke、Fixture、Baseline、Report、Replay 和 Field Validation 从生产路径不可达；
- [ ] 安装包内每个文件都有明确生产价值、核心风险价值或依赖价值；
- [ ] 阶段 Gate、Evidence、状态机和 Schema 已随旧能力删除或合并；
- [ ] Planner、Reviewer 配置只在真实保留入口确有需要时存在；
- [ ] 依赖清单、锁文件、许可证和必要 Runtime 完整保留；
- [ ] 一个真实小型多页 Deck 可以端到端生成并打开；
- [ ] 正式安装包、外部入口和长期 Artifact 相比当前基线实现净减少。

以下事项不阻塞第一目标完成，但列为紧随其后的质量工作：

- [ ] 用明确文字安全区约束生成视觉；
- [ ] 不再在 P3.3 预览中使用全页 Raw Layer 与正文自由叠加；
- [ ] 实际元素占用边界与文字安全区不存在阻断性相交；
- [ ] 增加能够捕获阻断性图文相交的布局测试；
- [ ] 背景装饰和明确声明的非内容层允许跨区，但不能影响阅读；
- [ ] 图片中不出现重复正式文字、数字、公式或步骤编号。

需要注意：当前正式 P4 已禁止 Raw Layer 和整页 Raster 替代。本次截图问题来自 P3.3 预览合成和临时 `workflow-smoke` 路径。后续质量修复不能误删 P4 已经有效的可编辑性保护。

## 11. 防止再次膨胀

后续每项新增文件或机制必须回答：

1. 它保护哪一项用户能力或核心风险？
2. 是否可以扩展现有 Request、Deck Plan、Build Result 或统一入口完成？
3. 是否替代并删除了旧文件？
4. 用户或宿主是否必须理解它？如果必须，能否取消？
5. 它是否会形成新的阶段、状态、Gate、Evidence 或长期兼容负担？

不得再使用以下方式扩展项目：

- 为每个中间对象建立独立 Schema；
- 为每个异常建立新状态；
- 为每个历史案例保留长期生产兼容；
- 用更多测试数量代替真实输出质量；
- 把开发 Smoke、Replay 或 Field Validation 包装成用户功能；
- 把内部函数重新暴露成用户必须调度的阶段。

最终产品应当是一个可以直接使用的 PPT Skill，而不是要求用户理解其开发历史的工程验证框架。
