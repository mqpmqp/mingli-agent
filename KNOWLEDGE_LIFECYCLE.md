# 知识生命周期

概念采用 draft → reviewed → verified；规则另有 deprecated；证据采用 raw → reviewed → verified；基准采用 draft → approved。升级必须由人工评审显式完成，导入工具不会自动升级。

每层按 `bazi`、`yijing`、`ziwei`、`qimen`、`fengshui`、`reality` 分类。所有知识对象必须有唯一 ID、来源 ID、PDF 页码和原始位置。`source_only` 规则禁止放入 verified；生产加载器忽略 `production_allowed=false` 的规则。
