# Meihua Governance v1 Implementation Report

## Decision

本次完成梅花易数第一阶段治理包，可进入人工审查：

```text
DRAFT_REVIEW_READY
```

这只表示输入、排卦口径、解释顺序和结算方式已经被写成可审计合同，不表示梅花易数的现实预测有效性已经得到证明。

## Audit basis

审计发现历史分支 `codex/meihua-yishu-knowledge-v1-20260821` 只包含一份 273 行的知识库草案，并且相对当前 `main` 已明显落后。草案中的基础内容有保留价值，但不适合直接合并，主要原因是：

1. 两数法已写明，三数显式动爻法未冻结；
2. 输入缺项只做“降级”，没有 fail-closed 状态码；
3. 事件类别、目标事件、成功标准和截止日没有形成不可覆盖合同；
4. 问题从一般事项补充为彻底迁移时，没有正式的 `QUESTION_DRIFT` 处理；
5. 应期只有原则性提醒，缺少方向/时间分开结算；
6. 没有 `occurred_at` 与 `observed_at` 区分；
7. 没有明确哪些案例不得计入准确率。

本轮没有直接 cherry-pick 旧分支，而是以当前 `main` 为基线重写治理协议。

## What

新增：

- `docs/meihua/README.md`
- `docs/meihua/INPUT_GATE_V1.md`
- `docs/meihua/CASTING_PROTOCOL_V1.md`
- `docs/meihua/INTERPRETATION_PROTOCOL_V1.md`
- `docs/meihua/SETTLEMENT_PROTOCOL_V1.md`
- `docs/meihua/templates/CASE_RECORD_V1.json`
- `MEIHUA_GOVERNANCE_V1_REPORT.md`

核心提升：

- 固定 `READY / NEEDS_CONFIRMATION / INPUT_CONFLICT / QUESTION_DRIFT / REPEAT_CAST / DATA_INSUFFICIENT`；
- 固定两数字与三数字两套独立 profile，禁止隐式切换；
- 固定爻序、互卦、变卦和体用算法；
- 隐私事件只要求类别、成功标准、截止日和现实阶段，不强迫披露敏感细节；
- 长期迁移拆成批准、出发、到达、身份生效和稳定居住等节点；
- 方向判断与应期判断分开；
- 预测版本不可覆盖，方向和时间分别结算；
- 问题漂移、回顾性案例、重复挑卦和无证据反馈一律不计数。

## Scope

未修改：

- `spec/` 与 `knowledge/`；
- `src/` 运行时代码；
- 六爻、八字、紫微、奇门和 PWA；
- 真实案例或个人信息；
- 任何规则 lifecycle/status；
- 产品发布与商业验证状态。

## Verification contract

本轮文档包至少执行：

```text
python -m json.tool docs/meihua/templates/CASE_RECORD_V1.json
检查全部 Markdown 相对链接存在
检查 JSON 不含真实姓名、精确地址或联系方式
检查禁止性绝对词和产品准确率声明
检查合成夹具的 60/70/50 结构：雷水解、互水火既济、二爻变雷地豫、体震用坎
```

最终验证结果绑定本次提交和 PR 当前 head，不能使用历史分支结果替代。

## Known limits

- 当前只有协议，没有确定性 `src/mingli/meihua/` 实现和 CLI；
- 没有自动历法、节气、月令或时间起卦；
- 没有自动旺衰、卦辞爻辞、外应或应期解释；
- 三数字 profile 是项目显式约定，仍需单独来源审查，不能冒充唯一传统口径；
- 合成结构夹具只验证算法一致性，不验证预测准确率；
- 合格前瞻样本仍为 0，商业状态保持 HOLD。

## Next phase

下一阶段应只实现确定性排卦核心和输入冲突门禁：

```text
src/mingli/meihua/
  tables.py
  validation.py
  models.py
  chart.py
  case_record.py
  benchmark.py

src/mingli/meihua_cli.py
tests/test_meihua.py
```

该阶段仍不得自动生成吉凶或应期，只负责把同一输入稳定地算成同一结构，并拒绝 profile 冲突和问题漂移。
