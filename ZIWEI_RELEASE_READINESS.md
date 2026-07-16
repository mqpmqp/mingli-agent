# Ziwei Release Readiness

日期：2026-07-16

| 组件 | 决策 | 证据与限制 |
|---|---|---|
| 时间/输入确定性合同 | GO | 边界测试、稳定序列化、Schema、fingerprint 已验证 |
| Deterministic Ziwei engine | **GO（待独立审查/合并）** | `ziwei-traditional-natal@1.0.0` 已实现命身宫、五行局、十四主星、十四辅煞、四化、基础状态与五局固定盘；Draft PR 阶段 Hold 仍 ACTIVE |
| Ziwei Rule Layer | **NO-GO** | 合同与 evaluator 可用，但可靠规则内容为 0，覆盖 0/168 |
| Runtime Integration | GO（受限） | 接受 complete/partial/degraded 结构化命盘和来源规则；规则推断仍保持 low-only gate |
| Evidence Fusion | GO（接口） | reality claim/scope hard override 回归通过 |
| Yuan Integration | GO（接口） | 八段、受控 status/confidence、免责声明合同通过 |
| Real Case Benchmark | **NO-GO** | Schema/汇总框架可用；没有授权真实案例 |
| Commercial Release | **NO-GO** | 排盘、规则、校准和真实案例证据均不足 |

## 可进入下一阶段的范围

- 使用合成输入和固定盘验证历法、太阳时、fingerprint、命身宫、五行局、星曜、四化、缓存和异步隔离。
- 接入经过单独来源审查的规则卡，但默认保持 draft 和 Release Hold。
- 招募明确授权、完成匿名化且可撤回的真实案例用于离线验证。
- 对未来独立算法实现做双来源验证、边界 benchmark 和版本化迁移。

## Release Hold

Traditional Engine Hold 在 PR A Draft/Merge Gate 阶段仍为 ACTIVE；完成独立代码/来源审查并合并后才可解除。Rule Content Hold、Real Benchmark Hold 和 Commercial Release Hold 均保持 ACTIVE。

不得把确定性排盘等同于预测有效，不得在 0/168 规则状态下生成传统解释，不得宣传预测准确率，不得用于医疗、法律、投资或婚姻决定，不得自动把咨询记录用于训练。

解除传统引擎 Hold 仍需 PR A 独立审查与 Merge Gate。解除规则层 NO-GO 还需要来源卡、冲突审查与覆盖门禁。解除商业 NO-GO 另需真实案例校准、隐私/安全/法务与产品风险评审。
