# Phase 18 现实上下文统一模型与 Evidence Fusion Orchestrator

实现统一 Reality Context、字段别名归一、类型校验、canonical hash，以及按 `claim_id + scope` 的证据编排。优先级固定为：一致的 verified reality hard override；否则最高 priority；同级相反证据 unresolved。任何相反证据都保留在 provenance 中。

不新增预测规则，不修改旧 evidence API，不修改 `spec/knowledge`，保持 `prediction_validity=not_evaluated`。
