# 紫微时序与组合规则 V2 实现报告

## 结论

本工作流以新增版本化模块实现紫微组合与时序规则求值，没有修改冻结的 v1 排盘、规则、证据或运行时合同。求值只接受 `ziwei-traditional-natal@1.0.0` 的完整命盘，固定输出 `prediction_validity=not_evaluated`，并保持 Release Hold 为 `ACTIVE`。

规则行为覆盖是工程合同覆盖，不是预测准确率。内置合成事实只用于验证触发、排除、冲突和 unsupported 路径，分类固定为 `synthetic_contract_only`，准确率状态固定为 `not_assessed`。

## 版本化接口

- 结果 Schema：`ziwei-temporal-combination-result@2.0`
- 方法：`ziwei-temporal-combination@2.0.0`
- 规则集：`ziwei-temporal-combination-rules@2.0.0`
- 兼容命盘算法：`ziwei-traditional-natal@1.0.0`
- 公共入口：`evaluate_ziwei_temporal_v2`、`load_ziwei_temporal_v2_rule_pack`、`build_ziwei_temporal_v2_coverage`

规则包和每条规则都带确定性 canonical hash；结果 hash 只包含规范化规则、命盘 fingerprint、排序后的发现、受限时间窗和已应用 Reality Evidence ID，不复制姓名、出生日期时间、时区、会话 ID 或完整命盘。

## 已实现行为

| 能力 | 确定性实现 |
|---|---|
| 四化组合 | 从同宫与几何关系中的 `lu/quan/ke/ji` 事实求值 |
| 主星/辅星组合 | 区分 primary、supporting、malefic，并按宫位生成规范 token |
| 三方四正 | 对每个锚定宫计算本宫、两组三合位和对宫 |
| 夹、拱、会、照 | 分别计算相邻双宫、两组三合翼、三方四正会聚和对宫照会 |
| 命身关系 | 规范化为同宫、对宫、三方或其他关系 |
| 亮度组合 | 以宫位、星曜和版本化亮度状态联合触发 |
| 大限、年、月叠加 | 严格校验 overlay 字段、目标宫、星曜、四化及 unsupported 状态 |
| 六主题 | 事业、财富、关系、学业、家庭、迁移都有可行为触发的规则 |
| 有界时间窗 | 大限最多十年；年与月分别限制为对应的 12 个月或单月窗口 |
| 冲突 | 低优先级规则被压制并降为 low；同优先级相反方向保留 unresolved 并降为 low |
| Reality Evidence | 仅 verified 且 claim/scope 完全相同的证据硬覆盖；不同 scope 不受影响 |
| fail closed | 拒绝非 complete、含 unsupported、算法不兼容、hash 被篡改、overlay 越界及事件预测请求 |

所有规则保持 `draft`，规则文本没有被升级为 `reviewed` 或 `verified`。输出的月精度窗口是候选观察窗口，不是事件发生预测。

## 行为覆盖门禁

一条规则只有同时通过以下真实求值路径才计入 covered：

1. canonical trigger 命中，且逐项删除任一触发 token 后不再命中；
2. 每个排除 token 都实际阻断命中；
3. 低优先级相反方向 peer 被压制，同优先级 peer 形成 unresolved conflict，并触发置信度降级；
4. chart 和 overlay 的 unsupported 路径都阻断命中。

测试对 trigger、exclusion、priority、conflict policy 和 unsupported exclusion 做重新哈希后的 mutation；即使合成 fixture 同步扩宽，偏离 canonical trigger 的记录仍不能成为 covered。coverage 结果始终同时返回 `accuracy_assessment=not_assessed` 和 `prediction_validity=not_evaluated`。

## 验证摘要

- RED：`PYTHONPATH=src python -m pytest -q tests/test_ziwei_temporal_v2.py` 因缺少 `mingli.ziwei_temporal_v2` 在 collection 阶段失败；RED checkpoint 为 `3e19aa9f796c05c31fc670576f1fff9c301c4a44`。
- focused GREEN：17 tests passed。
- coverage.py：目标模块 branch-aware coverage 为 81%，通过 `--fail-under=80`。
- Ruff：owned Python 文件无问题。
- compileall：owned Python 文件编译通过。
- frozen contract：78 个冻结文件全部匹配，0 violation。
- `git diff --check`：通过。

GREEN checkpoint 的精确 SHA 由提交完成后的交付信息记录；本报告与实现、Schema 和最终测试共同组成该 checkpoint。

## 非目标与剩余边界

- 未使用真实案例，也不提供准确率、命中率、校准度或商业有效性结论。
- 未实现具体事件、日期级事件点或保证性结果；请求 `event_prediction` 会被拒绝。
- 没有修改任何 frozen v1 文件、Release Hold、发布授权、外部服务或私人数据存储。
- 传统规则内容仍需独立领域审查；工程行为覆盖不能替代该审查。
