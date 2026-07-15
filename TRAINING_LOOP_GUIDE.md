# MingLi V2.0 Training Loop 使用指南

Training Loop 用于日常测算后的可审计改进，不是预测准确率 benchmark。用户说“很准”属于主观反馈；历史事实纠正用于修正上下文；后续事件属于 outcome observation；只有事前冻结 claim、隔离现实证据并经独立评分的结果才可能进入商业验证。

## 1. 数据准备

真实 training store 必须在 Git 仓库外。先通过既有 ETL 完成明确 consent、HMAC-SHA256 假名化、时区/经度处理和来源质量记录。CLI 只接收 `person:<64 hex>` case_id，不接收姓名、电话、微信、邮箱、证件号、精确地址或 HMAC salt。

一次运行输入至少包含：

```json
{
  "case_id": "person:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "created_at": "2026-07-15T12:00:00+00:00",
  "consent": {
    "analysis_allowed": true,
    "training_use_allowed": true,
    "consent_version": "training-consent@1"
  },
  "topic": "career",
  "chart_input": {
    "gender": "male",
    "calendar": "solar",
    "birth_date": "1990-03-15",
    "birth_time": "10:30",
    "timezone": "Asia/Shanghai",
    "birth_location": {"longitude": 121.47, "latitude": 31.23},
    "true_solar_time": false
  },
  "anchor_year": 2026,
  "reality": {},
  "fusion_evidence": []
}
```

`created_at` 属于输入合同。同一完整输入产生相同输出；程序不会偷偷加入当前时间。上例仅为合成数据，不能当真实案例或准确率证据。

## 2. 日常流程

以下示例中的 `D:\private\mingli-training` 必须替换为仓库外私有目录：

```powershell
mingli training run --input run.json --store D:\private\mingli-training --json
mingli training feedback --input feedback.json --store D:\private\mingli-training --json
mingli training outcome --input outcome.json --store D:\private\mingli-training --json
mingli training show --case-id person:<hmac-sha256> --store D:\private\mingli-training --json
mingli training review --store D:\private\mingli-training --create-iteration-at 2026-07-15T12:00:00+00:00 --json
mingli training candidates --store D:\private\mingli-training --json
```

`run` 依次执行 consent/privacy、Knowledge OS 内容校验、确定性 Phase 23 链、现实证据融合、置信门和 Yuan 八段渲染。没有 `training_use_allowed=true` 时可以完成已授权分析，但不会创建 case 或 run 记录。

反馈 JSON 包含评分、useful/inaccurate sections、missing context、用户纠正和提交时间。所有 feedback 都固定为 `counts_toward_accuracy=false`。outcome 记录事件时间与观察时间；普通自报结果仍不自动进入商业验证。

## 3. 人工规则审查

`review --create-iteration-at ...` 只会从明确的 inaccurate section、missing context 或历史纠正生成低置信 `pending_human_review` 候选。候选不包含原始自由文本，不会写正式 Knowledge/Rules，`applied_to_rules` 永远为 false。

人工审查者必须回看来源 run、支持证据、反证和现有 rule ID，再在独立变更中决定拒绝、继续研究或手动修改规则。Training Loop 本身没有批准或发布规则的权限。

## 4. 撤回与错误

```powershell
mingli training withdraw --case-id person:<hmac-sha256> --withdrawn-at 2026-07-15T12:00:00+00:00 --store D:\private\mingli-training --json
```

撤回会删除 case 及关联 run/feedback/outcome/candidate，失效关联 iteration，并留下不含 case_id 的不可逆摘要 tombstone 和 audit。常见稳定错误码包括：`TRAINING_STORE_INSIDE_REPOSITORY`、`TRAINING_CONSENT_NOT_GRANTED`、`PII_DETECTED`、`SCHEMA_INCOMPATIBLE`、`DUPLICATE_RECORD`、`CASE_WITHDRAWN`。

退出码：`0` 成功，`2` 存储/合同/隐私错误，`3` 产品 runtime blocked。
