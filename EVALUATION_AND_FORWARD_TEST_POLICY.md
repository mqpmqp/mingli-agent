# 实盘评测与 Forward Test 政策

版本：`evaluation-and-forward-test-policy@1.0`
实现：`mingli.forward_evaluation`

## 1. 目的

评测系统用于区分输入错误、预测合同错误、事件类别错误、时间错误和真正的现实反馈，防止事后改口或用商业行为替代证据。它不自动产生准确率，也不解除项目现有 release hold。

## 2. ForwardTestRecord

每个前向测试必须在结果可知前冻结：

- `test_id`；
- `prediction_id`；
- 实际使用的 `rule_ids`；
- 带时区的 `frozen_at`；
- 晚于冻结时刻的 `due_at`；
- `input_valid`；
- `prediction_valid`；
- 固定状态 `pending_forward_test`。

`due_at` 必须代表可以公允结算的事件窗口结束点。到期前调用结算会固定失败为 `FORWARD_TEST_NOT_MATURE`。

## 3. 允许与禁止的反馈来源

允许来源：

- `independent_observation`；
- `official_result`；
- `documented_reality`；
- `user_feedback_with_verifiable_artifact`。

明确禁止：

- `author_self_claim`；
- `payment_screenshot`。

未知来源 fail closed。付款行为、满意度或作者自称命中不证明具体预测成立。

## 4. 九类结果

| result | 定义 | 是否计入准确率分母 |
|---|---|---|
| `exact_hit` | 类别、条件和时间窗口均与冻结合同一致 | 是 |
| `partial_hit` | 命中部分已冻结主张，但并非全部 | 是 |
| `miss` | 主要主张未发生 | 是 |
| `timing_error` | 类别接近，但超出冻结时间窗口 | 是 |
| `category_error` | 发生了其他类别事件，不能算原预测命中 | 是 |
| `unmet_condition` | 冻结的成立条件未满足，结果不能直接归因 | 否 |
| `bad_input` | 冻结输入后来被判定不可靠或错误 | 否 |
| `no_feedback` | 到期但没有合格反馈 | 否 |
| `invalid_prediction` | 原预测不可证伪、范围不清或合同无效 | 否 |

代码对 `bad_input`、`invalid_prediction` 和 `no_feedback` 使用强制分类优先级，调用方不能用 `exact_hit` 覆盖它们。

## 5. 结算顺序

```text
校验时刻和到期状态
  -> 拒绝不合格反馈来源
  -> 校验结果枚举
  -> input_valid=false ? bad_input
  -> prediction_valid=false ? invalid_prediction
  -> 无结果 ? no_feedback
  -> 使用显式结果
  -> 生成确定性 EvaluationReceipt
```

同一 `ForwardTestRecord`、`as_of`、结果、反馈来源和反证会生成相同 canonical hash。

## 6. 反证与条件

结算收据必须保留 `counterevidence`，不能只记录有利反馈。成立条件未满足时使用 `unmet_condition`，不得把未发生事件解释为另一种命中。

时间窗口过宽、类别模糊或无法由现实资料判断的预测，应在冻结时标记 `prediction_valid=false`，到期后归为 `invalid_prediction`，而不是进入准确率统计。

## 7. 规则生命周期关系

新规则的生命周期固定为：

```text
raw
draft
reviewed
pending_forward_test
production
rejected
```

生命周期不是自动状态机。规则进入 `pending_forward_test` 后仍不能进入付费生产选择；只有经过独立审核并显式标记 `production` 才可被 `production_rules` 选中。单个 forward test 的有利结果也不会自动升级规则。

## 8. 统计声明边界

- 当前实现只分类单条收据，不计算产品准确率；
- 不使用 Silver、自述、付款或无反馈记录开启准确率声明；
- 聚合统计必须另行定义版本、分母、排除规则、盲评和独立审核；
- `exact_hit` 不能脱离完整样本集单独宣传；
- 本地合成测试只证明程序合同，不证明命理效果。

## 9. 数据和生产边界

本升级没有读取或写入 Git 外真实验证 store，没有揭盲任何 forward test，没有接触真实用户资料，也没有改变 `real_case_learning_v2` 的既有资产。部署、生产数据迁移和真实实盘结算仍需另行授权。
