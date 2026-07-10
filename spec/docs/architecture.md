# Architecture Baseline

## 运行链路

User
→ Intake / Intent Router
→ Deterministic Chart Adapter
→ Diagnosis
→ Rule Retrieval
→ Evidence Fusion
→ Reality Override
→ Timing
→ Confidence Gate
→ Yuan Renderer
→ Final Answer

## 模块边界

### Deterministic Chart Adapter
负责四柱、藏干、十神、大运、流年、五行量化。
不得输出人生结论。

### Rule Retrieval
根据结构化盘面与问题召回规则。
不得直接生成最终文本。

### Evidence Fusion
组合支持、反证和权重。
不得忽略现实硬条件。

### Reality Override
当前事实优先。
可否决盘面导出的不现实结论。

### Timing
只描述时间窗口与主题触发。
不得把“冲、合、桃花、财星”直接写成具体事件。

### Renderer
负责表达，不新增事实或规则。

## 失败策略

- 排盘不可用：停止精确判断，明确只能低置信分析。
- 规则无匹配：不补造规则。
- 现实信息缺失：提出最少必要问题，或降为低置信。
- 多规则冲突：同时保留支持与反证，降低置信。
