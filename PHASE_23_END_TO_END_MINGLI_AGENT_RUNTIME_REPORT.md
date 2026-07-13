# Phase 23：端到端 MingLi Agent Runtime

P23 已把 `chart → chenggu → reality_fusion → five_year → renderer` 串成确定性运行链。每阶段记录 artifact hash，整体记录 canonical hash；相同输入必须得到相同结果。

Runtime 不调用网络、LLM、数据库或缓存。出生资料由既有确定性排盘引擎和 P19 处理；现实证据由 P18 编排；P21 只输出趋势；P20 输出八段文本。领域基础状态仍是显式上游合同，Runtime 不会从出生资料自行创造未经审核的新规则。所有层级保持 `prediction_validity=not_evaluated`。
