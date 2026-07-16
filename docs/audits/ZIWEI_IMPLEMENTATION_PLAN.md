# 紫微能力补全实施计划

## 架构原则

1. 使用现有历法与太阳时算法做输入归一化，不复制八字柱计算。
2. 排盘结果分为 `complete`、`partial`、`degraded`、`refused`；没有可靠安星算法时必须 `partial/degraded` 并列出 `unsupported_fields`。
3. fingerprint 基于规范化排盘身份，不包含姓名、年龄、昵称、会话 ID。
4. 规则层只消费有 provenance 的事实；无合法规则卡不允许 LLM 补写传统结论。
5. 紫微结构证据进入 Phase18，Reality Context 仍按 claim/scope hard override。
6. Yuan 适配只提供受控 status/confidence，不改变既有八段合同和免责声明。

## 阶段与验收

| 阶段 | 交付 | 验收 |
|---|---|---|
| P0/1 | 审计、矩阵、计划、工作日志 | 文档与基线一致 |
| P2/3 | Schema、时间归一化、partial chart shell | 合法/非法/边界测试 |
| P4 | fingerprint、scope、revision、cache/pair 隔离 | 陈旧请求与串盘负向测试 |
| P5 | 规则卡、 evaluator、覆盖清单 | priority/exclusion/missing fact/conflict 测试 |
| P6 | Evidence Fusion/Yuan 适配与 CLI | reality override、八段、免责声明、smoke |
| P7 | 聚焦、相关、完整门禁 | 全部真实执行 |
| P8/9 | 匿名案例与隐私治理合同 | consent/withdrawal/schema 测试 |
| P10 | 三份最终报告与 Release Gate | 状态与代码/测试一致 |

## 明确不实施

- 未经可靠来源验证的命宫、身宫、局数、安星、四化、庙旺、格局算法。
- 大规模传统解释文本、外部网站输出复制、真实案例编造或未授权训练。
- 付费服务、生产部署、远端 push/PR/merge。

## 预期发布判断

- 确定性输入/隔离/合同底座：完成验证后可 GO。
- 紫微传统排盘引擎与规则内容：维持 NO-GO，直到独立来源、算法审查和 benchmark 齐备。
- Runtime/Yuan 接口：在只输出受控低置信、明确 unsupported 的前提下可 GO 进入真实案例验证准备。
- 商业发布：NO-GO。
