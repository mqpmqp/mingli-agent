# 小时训练规则晋升运行手册

## 目标与边界

本闭环让小时训练对 Runtime 产生可审计的实际作用，同时禁止“训练报告直接改生产规则”。V1 只支持三类受控变化：

- `runtime_instruction`：加入 MCP 的人工批准指令；
- `output_forbidden_phrase`：在 Runtime 最终文本中拦截指定表述；
- `output_required_notice`：在固定免责声明之前补充指定提示。

这三类变化只证明工程合同可执行，不证明八字、奇门或风水预测有效。领域算法、阈值和传统判断规则仍须走各自的规则卡与真实案例协议。

## 门禁顺序

| 阶段 | 写入记录 | 通过条件 |
|---|---|---|
| 小时报告 | `hourly_reports` | Schema、隐私扫描、来源 ID 已登记 |
| 候选与去重 | `promotion_candidates` | 规范化 domain/kind/statement/value 的内容键去重；新增来源会刷新候选 hash |
| 来源核验 | `source_checks` | 文件 SHA-256 身份一致，且每个来源已由人工标记 `reviewed` 或 `verified` |
| 回归 | `promotion_regressions` | 文本规则同时覆盖触发/不触发样例；提示指令通过单行、长度和覆盖指令 denylist |
| 人工批准 | `promotion_approvals` | 审批收据绑定当前 candidate hash、来源收据和回归收据 |
| 版本发布 | `rule_releases` | 每个候选都有通过门禁的人工批准；同一文字不得同时 required/forbidden |
| Runtime 加载 | Runtime receipt | 发布 manifest hash 可重算，当前来源仍处于已审状态 |
| Phase 4.1 | 现有真实案例协议 | 冻结预测时把 release `version` 写入 `rule_set_version`；结果到期后独立结算 |

任何候选内容或来源集合变化都会让旧收据失效。来源后来被改为 `rejected` 时，旧发布版本也会拒绝加载。

## 输入样例

来源元数据 `source.json`：

```json
{
  "title": "来源标题",
  "source_type": "pdf",
  "source_family": "author-edition-family",
  "scope_note": "只审查指定页码与候选规则作用域",
  "registered_at": "2026-09-13T12:00:00+00:00"
}
```

登记只计算文件内容哈希，状态固定为 `pending_human_review`。来源审查 `source-review.json` 必须使用不可逆 reviewer pseudonym：

```json
{
  "source_id": "source:64位sha256",
  "review_state": "reviewed",
  "reviewer_id": "reviewer:64位sha256",
  "reviewed_at": "2026-09-13T12:10:00+00:00",
  "review_note": "已核对文件身份、页码与作用范围"
}
```

小时任务需输出 `hourly_training_report.schema.json` 对应的 JSON。`report_id`、`report_hash` 和候选 ID 均由程序生成；自动化不得填写。报告里的直接身份信息会被拒绝。

人工批准 `approval.json`：

```json
{
  "candidate_id": "candidate:64位sha256",
  "source_check_id": "source-check:64位sha256",
  "regression_id": "regression:64位sha256",
  "decision": "approved",
  "reviewer_id": "reviewer:64位sha256",
  "review_note": "同意进入开发与真人试点范围",
  "decided_at": "2026-09-13T12:30:00+00:00"
}
```

发布输入 `release.json`：

```json
{
  "version": "hourly-rules@2026.09.1",
  "created_at": "2026-09-13T12:40:00+00:00",
  "candidate_ids": ["candidate:64位sha256"]
}
```

## Runtime 加载

新增的版本化适配器 `mingli.rule_runtime_v1.RuleAwareRuntime` 在不修改冻结 Phase 23/service 合同的前提下加载发布版本。命令行入口为：

```bash
mingli-rule-runtime capabilities --store /private/mingli-training --version hourly-rules@2026.09.1
mingli-rule-runtime analyze --input runtime.json --store /private/mingli-training --version hourly-rules@2026.09.1
mingli-rule-runtime apply --domain qimen --input qimen-result.json --store /private/mingli-training --version hourly-rules@2026.09.1
mingli-rule-runtime runtime-instructions --store /private/mingli-training --version hourly-rules@2026.09.1
mingli-rule-runtime phase4-1-binding --store /private/mingli-training --version hourly-rules@2026.09.1
mingli-rule-runtime phase4-1-bind-prediction --input prediction.json --store /private/mingli-training --version hourly-rules@2026.09.1
```

宿主服务也可以调用 `configured_rule_runtime(repository_root=...)`，通过以下环境变量选择仓库外训练 store 和可选固定版本：

```text
MINGLI_RULE_RELEASE_STORE=/private/mingli-training
MINGLI_RULE_RELEASE_VERSION=hourly-rules@2026.09.1
```

`analyze` 运行现有八字 Runtime；`apply --domain` 让奇门或风水宿主把自己的结构化结果送入同一发布规则适配器。省略版本时加载按 `created_at + version` 排序的最新发布版本；未配置 store 时适配器返回 `None`，宿主保持原 Runtime 行为。配置了不存在、篡改或来源已撤销的版本时会 fail closed。适配器的 capabilities 和分析结果返回版本、manifest hash、应用候选 ID、试点状态。

现有 `mingli-service` 属于冻结基线，本变更没有暗改它。把新版适配器接到已部署 HTTP/MCP/Telegram 进程、设置环境变量、重启或发布均属于后续部署步骤，必须在目标环境和版本明确后单独执行。

## 自动采集服务

新增的 `mingli-integrated-service` 保留原 Runtime 工具，并增加受认证的 `submit_hourly_training_report`、`get_rule_promotion_status` 和 `list_rule_review_queue`。写入工具调用 `TrainingReportCollector`，自动完成报告摄取、内容去重、来源门评估和合同回归；返回值始终显式标记 `auto_approved=false`、`auto_published=false`。

ChatGPT 不能用自定义 API Key 连接写入型 MCP，因此公网接入必须配置 OAuth 2.1/OIDC 资源服务器。部署、scope、持久卷、任务提示词和三任务冒烟步骤见 `docs/deployment/hourly-training-collector.md`。

## Phase 4.1 真人验证

每个发布 manifest 固定携带：

```json
{
  "pilot_target": 10,
  "registered_real_cases": 0,
  "accuracy": null,
  "prediction_validity": "not_evaluated",
  "commercial_release_hold": "ACTIVE"
}
```

真人样本必须在看到现实结果之前冻结预测，并把活动发布版本精确写入现有 V2 预测合同的 `rule_set_version`。小时训练案例、合成回归、主观反馈、未授权案例和事后解释均不得计入准确率。V1 不自动解除商业 Hold。
