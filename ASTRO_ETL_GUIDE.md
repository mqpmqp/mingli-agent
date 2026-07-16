# Astro 来源资料安全导入

`scripts/astro_etl_pipeline.py` 将一个已获得明确授权的 Astro 来源记录转换为 `RealCaseIntake`，然后交给现有受控 validation store 导入流程。原始资料、project salt 和导入后的完整案例都必须位于 Git checkout 之外。

仓库内可直接使用 `.venv-validation`。独立工具包另附当前项目 wheel；在已经具备项目依赖的受控 Python 3.11+ 环境中，可先运行 `python -m pip install .\mingli_agent-2.0.0-py3-none-any.whl`，再执行同目录的 `astro_etl_pipeline.py`。安装不会包含任何真实案例或 project salt。

## 必要边界

- `public_domain_historical` 不是本项目认可的 consent；缺少明确研究与 benchmark 授权时，转换会 fail closed。
- `events` 是已知结果，不能转换成预测前登记的 `scenarios`；输入含非空 `events` 时会拒绝。
- 姓名和来源记录 ID 只用于 HMAC-SHA256 假名化，不会写入输出；project salt 不会写入或打印。
- 经度换算结果标记为 `local_mean_solar_time`。因为没有应用时差方程（equation of time），`true_solar_time` 固定为 `false`。
- Rodden rating 不会自动决定 Gold/Silver。证据等级必须在后续现实证据、盲审与裁决流程中独立建立。
- 本步骤只产生 intake；现实事件必须等 prediction freeze 后，按 `RealityEvidence` 流程独立采集。

## 输入字段

输入是单个 JSON object，至少包含：

- `source_record_id`
- `birth_datetime_utc`（UTC ISO 8601）
- `birth_timezone`（IANA timezone，例如 `Asia/Taipei`）
- `birth_longitude`（-180 至 180）
- `birth_location_precision`、`birth_source`、`birth_confirmation_status`、`gender`
- 完整 `consent` 与 `case_metadata`
- 至少一个预测前登记且 `known_at_prediction_time=true` 的 `scenarios` 项

字段结构以 `validation/templates/real_case_intake.template.json` 和 `validation/templates/consent_status.template.json` 为准。不得把填入真实资料的副本提交到 Git。

## 运行

先执行 dry-run：

```powershell
.\.venv-validation\Scripts\python.exe scripts\astro_etl_pipeline.py `
  --file D:\private\authorized-astro-record.json `
  --store D:\private\mingli-validation `
  --source-ref authorized:astro-program `
  --project-salt-file D:\private\mingli-project-salt.txt `
  --dry-run
```

确认输出中 `validated` 为 `1`、`imported` 为 `0` 后，移除 `--dry-run` 执行实际导入。实际导入使用现有 atomic batch、duplicate detection 和 rollback manifest，不会直接写入 Git checkout。

等价的 package CLI 是：

```powershell
python -m mingli.cli validation astro-intake --file ... --store ... --source-ref authorized:... --project-salt-file ... --dry-run
```
