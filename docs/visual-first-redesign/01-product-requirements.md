# 视觉优先三阶段产品需求

> **Status**：Target Requirement（目标需求，尚未实施）
> **Document type**：Product Requirements（产品需求）
> **Authority**：定义未来目标体验，不覆盖当前正式 Runtime
> **Current runtime relationship**：当前 [`scripts/run.py`](../../content-to-editable-ppt/scripts/run.py) 直接构建路线保持不变
> **Depends on**：用户需求、现有 Skill 能力边界、[Accepted ADR](../../DECISIONS.md)
> **Next decision gate**：Stage 2 Benchmark `Passed` 后才允许进入新 ADR
> **Last updated**：2026-08-28

---

## 1. 产品只解决三个核心转换

```text
① 用户意图 → PPT 大纲和 Markdown 线框
② 大纲和线框 → 高质量 PPT 设计图
③ 已确认设计图 → 可编辑 PPT
```

最终目标：

```text
内容组织正确
+
视觉设计足够专业
+
可编辑重建足够可靠
```

---

## 2. Stage 1：内容权威

Stage 1 负责：

- 理解用户意图；
- 读取材料；
- 组织 Storyline；
- 形成整套 PPT 大纲；
- 形成逐页正式内容；
- 形成 Markdown 线框。

Stage 1 不负责：

- 最终配色；
- 最终字体；
- 精确坐标；
- 图片生成；
- PowerPoint 构建。

第一次正式确认后，以下内容成为下游正式内容 Authority：

- 标题；
- 正文；
- 数字；
- 专名；
- 表格数据；
- 引语；
- 核心结论；
- 页面顺序和主要组织关系。

Stage 2 如需修改正式内容，必须返回 Stage 1 并重新确认。

---

## 3. Stage 2：视觉权威

Stage 2 负责：

> 在不改 Stage 1 正式内容的前提下，把每页设计成专业、统一、多样并适合重建的 PPT 页面。

高质量至少要求：

- 第一眼专业；
- 构图稳定；
- 信息层级清楚；
- 页面类型与内容匹配；
- 留白合理；
- 多页风格一致；
- 页面之间有构图变化；
- 不滥用卡片；
- 不编造事实、数字、专名；
- 对 Stage 3 重建友好。

---

## 4. Representative Design Gate

Stage 2 不应直接生成整套。

建议先生成代表性视觉页，例如：

```text
封面
+
普通正文
+
复杂信息页
```

然后进入：

```text
Representative Design Gate
```

它只用于：

- 提前发现视觉方向错误；
- 提前发现卡片化、构图或密度问题；
- 避免整套生成后全部返工；
- 控制生成成本。

它不是正式 Approval，也不能产生 `Approved Design Preview`。

---

## 5. 第二次正式确认：全套视觉权威

代表性视觉 Gate 通过后：

```text
生成全套设计图
↓
页面级视觉审核
↓
跨页一致性审核
↓
用户全套审阅
↓
第二次正式确认
```

只有此时，全套设计图才成为：

```text
Approved Design Preview
```

即 Stage 3 的正式视觉 Authority。

这里的 `Approved Design Preview` 是未来产品中的权威概念，不代表恢复精简阶段已经删除的旧 P3 Artifact、Schema、State 或 Gate。

---

## 6. 设计图与正式文字的关系

始终保持：

```text
Stage 1 已确认内容
= 文字 / 数据 / 事实 Authority

Stage 2 已确认设计图
= 视觉 Authority
```

所以生图模型即使出现：

- 个别错字；
- 字形异常；
- 乱码；

Stage 3 的正式 PowerPoint 文本仍应来自 Stage 1，而不是从设计图反向抄写错误文字。

---

## 7. Stage 3：可编辑重建

Stage 3 负责：

> 把已确认设计图高保真重建成真正可编辑的 PowerPoint。

原则：

- 不重新设计；
- 不重写内容；
- 主要构图、层级和空间关系保持一致；
- 文字优先原生 PowerPoint Text；
- 简单图形优先原生 Shape / Connector；
- 标准图标优先可编辑 SVG；
- 图表优先可编辑结构；
- 复杂插画、照片、纹理可以保留为对象级资产；
- 不允许整页位图冒充“可编辑 PPT”。

核心保真原则：

> 感知结构保真优先于像素级保真。

---

## 8. 三阶段边界

| 阶段 | 决定什么 | 不决定什么 |
|---|---|---|
| Stage 1 | 内容、故事线、页面职责、粗略线框 | 最终视觉风格和精确布局 |
| Stage 2 | 视觉系统、构图、视觉层级、最终设计图 | 正式文字与事实 |
| Stage 3 | 如何高保真重建为可编辑 PPT | 不重新设计、不改内容 |

---

## 9. 当前直接构建路线

本研究不改变当前正式入口。

当前正式多页流程仍只有一次页面方案确认；本文定义的两次正式确认属于未来目标体验，尚未进入 `SKILL.md` 或 Runtime。

当前：

```text
content-to-editable-ppt/scripts/run.py
= Current Direct-Build Route
```

其输入合同仍是当前 [`deck-build-request.schema.json`](../../content-to-editable-ppt/schemas/deck-build-request.schema.json)，由 Host 提供精确英寸坐标和已确认内容。

只有在：

```text
Stage 2 Benchmark = Passed
+
新 ADR Accepted
+
Runtime 迁移验证完成
```

后，才允许由新 ADR 决定它是否转为未来 `Fast Mode`。

现有：

```text
content-to-editable-ppt/scripts/run_pipeline.py
= Single-Slide Compatibility
```

继续作为图片到单页可编辑 PPT 的兼容入口，其现有正式契约不由本文修改。

---

## 10. 非目标

本轮不是为了：

- 一次性重写整个 Runtime；
- 合并多个 GitHub 项目的完整 Runtime；
- 新增大量 Specialist Agent；
- 在 Benchmark 前锁死图片模型；
- 在 Benchmark 前锁死 Stage 2 Anchor；
- 未经 ADR 替换当前正式多页入口。
