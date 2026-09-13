# Phase 4.1 真人案例 Runtime 写入实现报告

## 结论

集成 Runtime 原先只有案例底层存储与已发布规则版本绑定，没有对外真人案例生命周期接口，且规则晋升状态把 `registered_real_cases` 固定为 0。本次增加同一私有训练 store 内的 append-only Phase 4.1 账本，并向 MCP/HTTP 暴露候选登记、筛选、预测冻结、反馈、追溯审计和状态读取。

## 强制链路

```text
候选登记 → 同意/隐私/输入筛选 → 预测冻结与 slot 分配 → 现实反馈 → 独立复核
```

系统强制 `received_at <= screened_at < frozen_at <= submitted_at`。任何已经产生预测、冻结或反馈的案例只能登记为 `intake_sequence_violation`；可以进入 `observed_real_cases` 作为真人审计证据，但不得进入 `registered_real_cases`、准确率或正式 pilot slot。

## 接口

| MCP 工具 | HTTP 路由 | 权限 | 作用 |
|---|---|---|---|
| `submit_phase4_1_candidate_intake` | `POST /v1/training/phase4-1/candidates` | `training:write` | 不可变候选收据 |
| `screen_phase4_1_candidate` | `POST /v1/training/phase4-1/screens` | `training:write` | fail-closed 筛选 |
| `freeze_phase4_1_prediction` | `POST /v1/training/phase4-1/predictions` | `training:write` | 冻结预测与顺序 slot |
| `submit_phase4_1_feedback` | `POST /v1/training/phase4-1/feedback` | `training:write` | 冻结后反馈 |
| `submit_phase4_1_retrospective_audit` | `POST /v1/training/phase4-1/retrospective-audits` | `training:write` | 时序违规审计 |
| `get_phase4_1_status` | `GET /v1/training/phase4-1/status` | `training:read` | 计数与完整性 |

## 安全边界

- 复用 `TrainingStore.root`，没有第二套 storage。
- 记录只允许去标识 SHA-256 ID、哈希和有限 evidence/topic code，并在写入前运行既有 PII 扫描。
- synthetic candidate 永不占真人 slot。
- slot 只在合格候选完成预测冻结时按连续顺序分配。
- 反馈固定 `counts_toward_accuracy=false`，准确率仍需独立审核。
- 不执行来源审核、候选批准、规则发布或 Release Hold 解除。

## 第二例处理原则

当前第二例已在候选收据之前生成预测并取得多项反馈，因此只能以 `prior_stage=feedback_received` 写入并形成追溯审计。正式状态应是 `observed_real_cases +1`、`sequence_violations +1`，而 `registered_real_cases` 不增加。下一例必须先调用候选登记工具，才可成为正式连续入组 slot。
