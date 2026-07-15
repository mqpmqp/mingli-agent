# Astro ETL TDD Evidence Report

## Source and journeys

需求来自用户提供的损坏 `astro_etl_pipeline.py` 与生成记录；没有单独的 plan 文件。

- 作为 validation operator，我希望只导入明确授权、已假名化的 Astro 来源记录，以免 PII 或未授权资料进入案例库。
- 作为 benchmark reviewer，我希望已知事件不会被改写成 prediction 前登记的 scenario，以维持 prediction/reality 隔离。
- 作为命理计算维护者，我希望经度换算被准确标记为 local mean solar time，不虚称 true solar time。
- 作为 operator，我希望先 dry-run，并复用 atomic controlled-store import。

## RED / GREEN evidence

| Guarantee | Test | RED | GREEN |
|---|---|---|---|
| 授权记录转换为无 PII 的合法 intake | `test_authorized_record_becomes_valid_pseudonymous_intake` | 缺少 `mingli.validation_astro_etl`，import error | PASS |
| 公开资料不能替代明确 consent | `test_public_biography_without_explicit_consent_fails_closed` | 缺少 transformer | PASS |
| retrospective events 不得成为登记 scenario | `test_retrospective_events_are_never_registered_as_scenarios` | 缺少 transformer | PASS |
| LMT 校验经度与 UTC 输入 | `test_local_mean_solar_time_rejects_invalid_inputs` | 缺少 transformer | PASS |
| project salt 不进入输出 | `test_salt_never_appears_in_serialized_output` | 缺少 transformer | PASS |
| CLI dry-run 验证但不写 store | `test_cli_dry_run_validates_without_writing_to_store` | `astro-intake` 尚不存在 | PASS |
| transformer 不预先附加 hash，避免 import 二次 hash | `test_authorized_record_becomes_valid_pseudonymous_intake` | 输出含 `intake_canonical_hash` | PASS |

验证命令：

```powershell
.\.venv-validation\Scripts\python.exe -m unittest tests.test_validation_astro_etl -v
```

最终 targeted 结果：`Ran 6 tests ... OK`。

## Checkpoint commits

- `3b0c8a6` — 初始 RED contracts
- `031bde2` — transformer GREEN
- `c80b83e` — CLI 与 double-hash RED
- `2380811` — CLI integration GREEN

完整 suite、coverage、lint、type、security 与 diff gate 的最终结果记录在本任务最终验证输出中。
