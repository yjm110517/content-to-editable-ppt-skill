# Content to Editable PPT Skill 非功能需求与质量指标 v1.6

## 文档地位

本文档是 [v1.5](../v1.5/non-functional-requirements.md) 的增量权威版本。本版新增 P5 非功能需求。

## 完整性与确定性

- 正式交付 PPTX SHA-256 必须等于 P4 Candidate Deck SHA-256；
- 相同输入 + 相同 Packaging Runtime Lock → ZIP 字节/SHA-256 必须一致；
- 所有 P5 正式 JSON Artifact 使用 Canonical 序列化：RFC 8785 / JCS + Unicode NFC + UTF-8 + LF + No BOM；
- Packaging 是纯函数，只消费已冻结 Artifact，不产生新业务字段；正式 JSON 禁止 packaged_at、当前时间、随机 UUID、临时目录名、用户名、本机绝对路径；
- 时间类字段只有已冻结的 accepted_at_utc（Warning Acceptance）允许存在；
- Packaging Runtime Fingerprint 不一致时停止，不得用不同 zlib/Python 静默生成同名交付包。

## 可追踪性

- Source、Normalized、Sanitized、消费输入与交付文件 Hash 必须可追踪；
- Provenance 记录 P1–P4 Authority、Final Integrity、Roundtrip、Reviewer、Decision、Runtime Lock 与 6 个 sibling 交付文件 Hash；
- Provenance 自身 Hash 由 P5 State/Gate 记录（两层闭包）；
- 交付目录外不允许存在未声明文件；Roundtrip 副本、Raw Layer、Prompt、Raw Response、未接受 Revision 不得进入交付目录。

## 安全

- 任意路径逃逸、Symlink/Reparse Point、源文件篡改或未知图标名必须失败；
- 交付目标已存在时仅在完整文件集合与 Hash 全部一致时视为幂等成功，否则拒绝覆盖；
- 宏、OLE、外部关系、链接媒体和活动内容必须为 0 或显式审计通过。

## 环境

- 开发与 Gate 环境为 Windows x64 + Microsoft PowerPoint Desktop COM；
- Renderer Identity / Version / Dimensions 必须与 P4 Post-Assembly Renderer Evidence 一致；Renderer 环境变化返回 P4 Revalidation；
- 依赖冻结：python.zipfile、zlib、Pillow、rfc8785，不新增 P5 专属依赖。

## Reviewer 质量约束

- Unexpected Reviewer Calls = 0（未绑定 QA issue 的调用）；
- Issue-bound Reviewer Calls ≤ 预算（batch_size ≤ 4、batch_calls ≤ 2）；
- review_incomplete 在 P5 永远 Blocking；
- Deck Consistency Review 不得重开已通过的 P4 页面级 Fidelity 判断；
- 超过 8 个异常页 → systemic_visual_failure → 返回 P4。
