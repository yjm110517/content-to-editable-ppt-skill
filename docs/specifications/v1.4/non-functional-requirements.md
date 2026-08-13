# Content to Editable PPT Skill 非功能需求与质量指标 v1.4

- 正常解析必须离线、确定性并可解释。
- 固定输入和固定 Vendor 必须产生相同索引、候选排序与物化结果。
- Source、Normalized、Sanitized 和消费输入 Hash 必须可追踪。
- 任意路径逃逸、Symlink/Reparse Point、源文件篡改或未知图标名必须失败。
- Resolution Record 和历史 Artifact 不得覆盖。
- Tabler、resvg 和平台版本必须进入锁文件及 Gate Evidence。
