# Phase 22：真实案例 Benchmark 与前事回测

P22 已完成案例注册表、资格门禁、受控标签比较、逐案例计分、汇总指标与 CLI。真实案例必须同时满足 `consent_status=granted`、`deidentified=true` 和非空 `source_ref`；合成案例永不进入准确率分母。

仓库当前没有符合这些条件的真实案例，故结果为：`eligible_real_cases=0`、`exact_match_rate=null`、`product_accuracy_claim_allowed=false`。这不是测试失败，而是防止伪造案例与虚假产品声明的硬边界。后续需由获授权的数据流程导入不少于 30 个合格案例，且回溯精确匹配率仍不能代替前瞻有效性验证。
