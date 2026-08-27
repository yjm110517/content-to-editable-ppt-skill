# 阶段 3：删除旧体系、核心验收与文档收口

## 文档状态

- 状态：已完成，待合入
- 前置文档：[阶段 2：建立并原子切换多页主入口](02-single-entry-cutover.md)
- 总计划：[Content to Editable PPT Skill 精简计划](../skill-simplification-plan.md)

本阶段是仓库改造批次，不是 Skill Runtime 阶段或用户状态。它在同一条可回退分支中完成旧 P1～P5 多页体系删除、核心验收和文档权威收口；历史恢复依赖 Git，不创建归档目录、兼容层或新的证据体系。

## 已实施的删除与收敛

1. 删除 Deck Consistency、Exception Reviewer、P5 Delivery State、Gate、Evidence、Packaging Runtime，以及相应 Schema、测试、Fixture 和工具。
2. 删除旧 P1 Content Plan、P2 Wireframe、P3 Visual System/Preview、P4 Reconstruction 的运行闭包及互相依赖的评估器。
3. 从 Agent 配置和调用适配器移除 Deck-only Mode，完整保留单页 `review` Profile。
4. 将旧 Reconstruction Renderer 收敛为共享 `render_deck.py`；将仍有价值的文件和像素 Hash 收敛为轻量媒体 Hash；`deck_roundtrip.py` 仅接收新多页 Slide Binding，同时保留内部 COM Worker 分发协议。
5. 删除无调用方的 Deck/P5 Warning Acceptance Schema；单页 Warning Acceptance 继续由 `run_state.json` 与 `create_delivery_decision.py` 实现。

保留边界固定为：

```text
多页：run.py
单页：run_pipeline.py
共享：资产、字体、PPT 构建、渲染、Roundtrip、QA
```

没有修改 `deck-build-request.json`，也没有削弱单页 Planner、Reviewer、Recovery、Warning Acceptance、Delivery Decision 或七文件交付。

## 核心验收

### 单页审核交付保护

新增紧凑专项回归，锁定以下单页行为：

- 最终迭代 Warning Candidate 经显式接受后产生 `pass_with_warnings` 并进入 `packaging`；
- 显式拒绝进入 `failed`，不能打包；
- Evaluation Hash 过期时拒绝创建 Delivery Decision，且不产生输出；
- 用户消息只按 NFC/LF 归一化计算 SHA-256，状态不保存原文。

### Windows + Microsoft PowerPoint 实机结果

已用临时目录生成三页直接 Deck：原生文字和形状、外部有效 PNG、原生 Chart。Build、PowerPoint Render、Open → SaveAs → Reopen → Render、Roundtrip 与 QA 均通过；正式输出目录恰好包含 PPTX 和 Contact Sheet Preview，诊断只留在独立 `work-dir`。

### 规模对比

| 指标 | 精简前 | 精简后 |
|---|---:|---:|
| 正式安装包文件 | 234 | 101 |
| Scripts | 100 | 57 |
| Schemas | 107 | 26 |
| References | 14 | 6 |
| Agent 文件 | 6 | 5 |
| Tests | 119 | 13 |
| 多页默认用户交付物 | 多文件证据包 | PPTX + 预览 |
| 核心 Runtime 回归 | 阶段开始时实测 | 53 项，1.28 秒（不含 PowerPoint 实机验收） |

数量是结果记录，不是机械门槛：每个保留文件仍须对应当前用户能力、核心风险、必要依赖或许可证/来源要求。

## 文档权威收口

README 与 `SKILL.md` 保持当前用户流程：多页由 `run.py` 直接构建，单页由 `run_pipeline.py` 独立兼容。旧多页实现已删除；Architecture v2.4、Specification v1.6、Contract v1.4 和 Testing v1.4 顶部标为历史，正文和已接受 ADR 不被改写。

本文件合并原阶段 4 的核心验证与文档收口职责；不保留独立阶段 4 文档。

## 最终验证

```powershell
python -m unittest discover -s tests/runtime -p "test_*.py"
python content-to-editable-ppt/scripts/verify_install.py --manifest <temporary-directory>/runtime-manifest.json
python content-to-editable-ppt/scripts/run.py --request <deck-build-request.json> --work-dir <new-work-directory> --output-dir <new-output-directory>
git diff --check
git status --short
```

还必须扫描正式代码，确认不存在旧 `manage_*`、P1～P5 Artifact、Deck Consistency、Exception Batch、Style Anchor、Prompt Package 或 Reconstruction 外部入口。单页 Canonicalization 的历史版本字符串可以保留，但不得有旧多页调用路径。

## 完成结论

`正式 Skill 瘦身完成` 的前提是上述核心 Runtime、安装、静态检查和 Windows + PowerPoint 实机验收全部通过。若任一核心能力回归，只回退对应功能簇提交；文档错误则独立修订。不得恢复 P0～P5、建立兼容层或改写已接受 ADR。

后续视觉质量工作应直接扩展精简后的 Deck Request 和多页主入口，以文字安全区、图片/文字边界和阻断性相交测试解决问题；不得恢复旧 P3/P4 用户阶段。
