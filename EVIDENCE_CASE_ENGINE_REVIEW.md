# Evidence & Case Engine v0.1 Review

## 目标与非目标

本阶段建立证据分类、证据冲突排序、合成案例记录和案例边界评测，不增加排盘、预测或事件推断能力。冲突解析器只决定哪一层已有证据应优先，不生成新主张。

所有案例均为 `synthetic_boundary_case`，只包含为测试边界所需的抽象盘面标签、现实上下文和相对时间事件。没有姓名、生日、地点、联系方式、原始对话或其他私人命例资料。

## Evidence 模型

Evidence 类型明确区分：

- `traditional_source`：传统来源中的单一主张。
- `expert_rule`：经人工整理的专家边界规则。
- `reality_fact`：可确认的现实状态或硬条件。
- `case_observation`：案例内或多案例观察，不自动视为普遍规律。

优先级固定为：

`reality_fact > user_confirmed_event > multi_case_observation > single_traditional_claim`

Evidence 类型与优先级分开建模。例如，用户确认的事件属于现实或案例证据，但使用 `user_confirmed_event` 优先级；案例观察只有在确为多个独立案例时才能使用 `multi_case_observation`。

## Conflict Resolver

解析器要求所有输入针对同一 `claim`，且 polarity 只能是 support 或 contradict。它选择最高优先层：

- 最高层方向一致：返回 resolved，并列出被覆盖的低层证据。
- 最高层内部正反冲突：返回 unresolved，不选择任何一方。
- 空输入、混合主张、未知优先级或 polarity：明确失败。

该机制不会把案例观察提升为因果规则，也不会把现实结果倒推为命盘特征。

## Case 与 Event

Case 必须包含 source_id、chart_features、reality_context、event_timeline 和 verification_level。Event 必须包含独立 ID、source_id、相对 period、事件类型、观察与验证等级。

首批 6 个合成案例覆盖：财星旺但现实贫困、财星弱但现实富裕、官星弱但成功上岸、桃花旺但婚姻稳定、七杀明显但事业成功、食神格长期压力。它们用于证明“盘面标签不能覆盖现实”，不是经验样本，更不是训练数据。

## Benchmark 与生命周期

新增 30 个 draft 案例边界测试，每条回链 case、evidence 和 exclusion。测试覆盖证据覆盖顺序、禁止倒推命盘、禁止扩大为未来预测、禁止自动财富/婚姻/疾病判断。

本阶段所有 Evidence 和 Case 最高为 reviewed，Benchmark 为 draft；没有自动 verified。任何真实案例未来进入仓库前，必须另行完成授权、匿名化、用途限制、删除机制和人工审查。

## 已知限制

- 合成案例不能支持统计或因果结论。
- `multi_case_observation` 目前仅用于解析器与边界测试，不代表已有真实多案例数据。
- resolver 只处理单一 claim 的证据层级，不做概率评分、预测或跨 claim 推理。
