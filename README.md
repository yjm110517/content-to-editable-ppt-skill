# Content to Editable PPT Skill

`content-to-editable-ppt-skill` 的目标是把主题、文档或大纲转换为多页、可编辑的 PowerPoint 演示文稿。

## 当前状态

本仓库目前处于引导阶段。首个版本继承了 `Image to Editable PPT` 项目中可复用的 PowerPoint 构建、字体审计、资产处理、渲染、结构 QA 和视觉审核基础设施，并为新 Skill 完成了独立仓库和身份迁移。

当前继承的可执行流程仍以“参考图片 → 可编辑单页 PPT”为主。以下能力尚未实现，不能视为当前承诺：

- 主题、文档或大纲的结构化输入；
- 多页叙事规划与页面类型选择；
- 跨页主题、字体和版式一致性；
- 图表、引用和来源管理；
- 面向完整演示文稿的多页视觉审核。

## 计划中的调用接口

Skill 名称和安装目录已经确定：

```text
$content-to-editable-ppt
content-to-editable-ppt/
```

在内容输入和多页输出契约完成前，该调用名主要用于开发、验证和扩展继承的运行时，不应对外宣称已经支持完整的内容到多页 PPT 工作流。

## 当前仓库结构

```text
content-to-editable-ppt-skill/
├─ README.md
├─ LICENSE
├─ NOTICE
└─ content-to-editable-ppt/
   ├─ SKILL.md
   ├─ agents/
   ├─ references/
   ├─ schemas/
   └─ scripts/
```

## 已继承的运行时能力

- 使用 PptxGenJS 构建原生文本、形状、线条和图片资产；
- 裁切、打包和校验图片或 SVG 资产；
- 审计字体并通过 PowerPoint 渲染结果；
- 检查对象、媒体、越界和可编辑性；
- 分离布局规划与独立视觉审核角色；
- 使用确定性 Schema、运行状态和交付门槛。

## 下一阶段

下一阶段将在不破坏现有构建与 QA 基础设施的前提下，设计内容输入、多页规划、主题系统、页面类型和完整演示文稿审核契约。相关接口会在实现和验证后再写入正式使用说明。

## 开发验证

Skill 基础结构可使用 Codex 的 `skill-creator` 校验器检查：

```powershell
python C:\Users\WINDOWS\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\content-to-editable-ppt
```

Node.js 运行时要求 Node.js 20 或更高版本。依赖声明位于 `content-to-editable-ppt/scripts/package.json`，Python 依赖声明位于 `content-to-editable-ppt/scripts/requirements.txt`。

## 许可证与来源

本项目采用 Apache License 2.0。继承代码的版权和来源说明保留在根目录及 Skill 目录内的 `LICENSE` 与 `NOTICE` 文件中。
