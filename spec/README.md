# MingLi Agent V2 Baseline

这是命理智能体的**可实现基线规范包**，不是已经运行的应用。

## 当前交付

- `system/system_prompt.md`：最高控制层
- `schemas/`：输入、命盘、证据、判断、现实、决策协议
- `rules/`：首批可审查规则卡
- `routing/intent_router.yaml`：任务路由
- `renderer/yuan_v2.md`：最终输出规范
- `evaluation/`：评测规范与黄金样例
- `docs/architecture.md`：架构边界
- `docs/productization_prd.md`：产品化 PRD
- `docs/implementation_backlog.md`：工程实施顺序
- `docs/codex_handoff.md`：Codex 恢复后的执行任务包

## 明确边界

1. 当前包不包含真实排盘算法。
2. LLM 不得自行推算四柱、大运、流年或紫微盘。
3. 所有精确盘面字段必须来自确定性算法或用户确认。
4. 规则卡属于候选知识资产，需要案例回测与人工审核。
5. 命理结论只作传统文化研究与娱乐参考。

## 推荐实施顺序

1. 数据协议与校验
2. 外部排盘适配器
3. 规则检索与证据融合
4. Reality Override
5. Yuan Renderer
6. MingLi-Bench
7. 资料导入与案例库
