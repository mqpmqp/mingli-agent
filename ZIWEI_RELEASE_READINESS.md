# Ziwei Release Readiness

日期：2026-07-16

| 组件 | 决策 | 证据与限制 |
|---|---|---|
| 时间/输入确定性合同 | GO | 边界测试、稳定序列化、Schema、fingerprint 已验证 |
| Deterministic Ziwei engine | **GO（Draft PR #28 CI 通过，待远端审查/合并）** | `ziwei-traditional-natal@1.0.0` 已实现命身宫、五行局、十四主星、十四辅煞、四化、基础状态与五局固定盘；benchmark false-pass 缺陷已按 TDD 修复；Draft/未合并状态下 Hold 仍 ACTIVE |
| Ziwei Rule Layer | **GO（本地工程门禁，内容审查待完成）** | 184 条 draft 规则可加载和求值；主星×宫位 168 records / 168 behaviorally evaluated；覆盖状态 `REVIEW_REQUIRED`，Rule Content Hold 仍 ACTIVE |
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

Traditional Engine Hold 的本地独立代码/来源审查已通过，PR A 已发布为 Draft，但合并前仍为 ACTIVE。Rule Content Hold 在 PR B 独立内容审查与合并前保持 ACTIVE；Real Benchmark Hold 和 Commercial Release Hold 继续 ACTIVE。

不得把确定性排盘或 168/168 工程覆盖等同于预测有效；draft 规则只能在明确规则求值入口中低置信运行，不得宣传预测准确率，不得用于医疗、法律、投资或婚姻决定，也不得自动把咨询记录用于训练。

解除传统引擎 Hold 仍需完成 PR A 远端审查与合并。解除 Rule Content Hold 还需要 PR B 独立内容审查、远端 CI 与合并；工程覆盖本身不解除 Hold。解除商业 NO-GO 另需真实案例校准、隐私/安全/法务与产品风险评审。
