# Case OS V2 受控场外 CLI 流程

本流程面向已获得授权的受控操作员。真实用户资料、同意书、原始问题、salt、
反馈和案例快照必须位于 Git checkout 外的受控存储。命令拒绝 checkout 内的输入或
输出路径，并以 `x` 模式写入新文件，禁止覆盖原始冻结快照。

所有命令的输出仍固定为 `commercial_release_hold=ACTIVE` 与
`prediction_validity=not_evaluated`。合成 fixture 仅用于合同测试，绝不能用于准确率、
校准或商业就绪主张。

## 场外快照序列

```powershell
# 1. 授权 intake + 排盘、规则、Reality Context、置信度和 Yuan 输出已在场外冻结后，创建 Case OS 起点。
python -m mingli.cli validation case-start --input D:\controlled\start.json --output D:\controlled\case-0001-frozen.json

# 2. 前事只允许记录在 prediction 生成前已发生且已知的事件；写入新的快照。
python -m mingli.cli validation case-prior --case D:\controlled\case-0001-frozen.json --evidence D:\controlled\prior-evidence.json --output D:\controlled\case-0001-prior.json

# 3. 未来反馈只能记录 prediction 冻结后开始的事件窗口；Reality Evidence 冲突会保留 hard override。
python -m mingli.cli validation case-future --case D:\controlled\case-0001-prior.json --evidence D:\controlled\future-evidence.json --output D:\controlled\case-0001-outcome.json

# 4. 基于事件和观察时间，而不是导入顺序，冻结 train/test 分区。
python -m mingli.cli validation case-partition --cases D:\controlled\eligible-cases.json --cutoff-at 2026-01-01T00:00:00Z --output D:\controlled\partition-v1.json

# 5. 双人独立审查与必要裁决后，场外请求必须包含 future evidence、无泄漏 test partition、错误分类、规则归因和 revision 建议。
python -m mingli.cli validation case-adjudicate --case D:\controlled\case-0001-outcome.json --request D:\controlled\adjudication-request.json --output D:\controlled\case-0001-adjudicated.json

# 6. 生成仅供人工处理的规则审查队列；此操作从不改写规则包。
python -m mingli.cli validation case-review-queue --cases D:\controlled\adjudicated-cases.json --output D:\controlled\operator-review-queue.json

# 7. 收到撤回时生成独立 tombstone，后续分区必须纳入该 tombstone。
python -m mingli.cli validation case-withdraw --case D:\controlled\case-0001-adjudicated.json --withdrawn-at 2026-01-03T00:00:00Z --output D:\controlled\case-0001-withdrawal.json
```

## 人工边界

- 两名独立审查员在裁决前不得互见结论；不一致时交由独立裁决者。
- `hit`、`partial`、`miss`、`unverifiable` 均需保留；非 hit 必须进入错误分类与负样本归档。
- `case-adjudicate` 的规则建议始终为 `pending_operator_review`，不会自动 promote 或 demote。
- 只有合规授权的、场外真实案例才可提供 `hold-reassessment` 的输入；即使门槛满足，它也仅允许独立复审，绝不自动解除 Hold。
