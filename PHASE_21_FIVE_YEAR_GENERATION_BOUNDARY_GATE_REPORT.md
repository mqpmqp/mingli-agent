# Phase 21：五年断事生成与边界门禁

P21 将五年输出限定为锚点年 `-2…+2` 的连续窗口。算法按领域基础状态叠加年度整数信号；已核验现实证据只覆盖同年、同领域，现实证据互相冲突时保持 `unresolved`。

本阶段只提供趋势状态，不生成事件。输入中的事件、金额、上岸结果、复合结果、婚期等字段会直接失败；每年输出固定带有 `trend_only_no_concrete_event`，总结果继续保持 `prediction_validity=not_evaluated`。P20 通过 `renderer_years(...)` 消费五年结果。
