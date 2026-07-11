# Phase 6 Batch 0/1 Derived Contracts Report

## 1. Baseline

- Repository: `mqpmqp/mingli-agent`
- Baseline / post-merge main: `6c1da420f7767f08aee93dea0f7500a328e785ca`
- Branch: `agent/phase6-derived-contracts-v0.1`
- Decision: `PHASE_6_R1_CONSERVATIVE_BOUNDARY_APPROVED`
- PR #8 closure head: `758b4aeb589f4ab71d6306d980d7622c678587cd`
- PR #8 merge commit: `6c1da420f7767f08aee93dea0f7500a328e785ca`
- Post-merge main push CI: run `29146822788`, success

工作从上述 main 的全新 clean worktree 开始；原 P0 worktree 未进入、未修改。

## 2. Scope

本批只完成 Batch 0 的 R1 capability/source manifest 基础，以及 Batch 1 的不可变数据合同、只读 base adapter、canonical serialization/hash、structured errors 和 package-owned JSON Schema。没有实现藏干、十神、纳音、旬空查询或任何派生业务算法。

## 3. R1 Decision Compliance

- 采用 `BaseChart -> DerivedStructure -> Interpretation` 分层；本批只建立 DerivedStructure 合同。
- Phase 5 `calculate()`、method ID、calculation version 和输出字段没有修改。
- Phase 6 固定 `schema_version=bazi-derived-structure-result@0.1`、`method_id=bazi-derived-structure@0.1.0`、`calculation_version=0.1.0`。
- profile 分开版本化为 hidden stems、ten gods、NaYin、XunKong。
- 所有结果固定 `prediction_validity=not_evaluated`；没有解释或预测字段。
- timeline、十二长生、relations、神煞及所有解释/预测均未实现。

## 4. Changed Files

- `src/mingli/contracts/`: models、serialization、source validation、schema loader 和五份 JSON Schema。
- `src/mingli/derived/adapter.py`: Phase 5 base result 的只读 allowlist adapter。
- `tests/test_derived_contracts.py`: 合同、错误、来源、wheel/package-data 测试。
- `tests/fixtures/phase6_capability_manifest_v0.1.json`: R1 capability 冻结清单。
- `tests/fixtures/phase6_source_manifest_v0.1.json`: 双来源及 independence group 清单。
- `pyproject.toml`: package-data 和仅开发用 `build` 依赖。
- 本报告。

未修改 `.github/workflows`、`spec/`、`knowledge/`、Phase 5 算法、Core Runtime renderer 或 Evidence Engine。

## 5. Data Contracts

实现 frozen dataclass：`BaseChartRef`、`DerivedConventionProfile`、`DerivedChartResult`、`DerivedPillar`、`HiddenStemRecord`、`TenGodRecord`、`NayinRecord`、`XunKongRecord`、`DependencyAmbiguity`、`DerivedError`。

`DerivedChartResult` 支持 `complete | partial | refused`。partial 必须至少有一个 ambiguity；complete 不得含 ambiguity/error。当前模型只定义结构形状，不执行五项映射。

## 6. Base Compatibility Matrix

| Base method ID | Version | 状态 |
|---|---|---|
| `bazi-deterministic-lichun-jie-noaa-v0.1` | `0.1.0` | supported |
| 其他任意组合 | 任意 | `DERIVED_BASE_METHOD_UNSUPPORTED` |

缺少/错误 pillars 或 conventions 返回 `DERIVED_BASE_RESULT_INVALID`；expected fingerprint 不一致返回 `DERIVED_BASE_FINGERPRINT_MISMATCH`。adapter 不猜测、不修正、不重算四柱。

## 7. Canonical Serialization

- UTF-8、Unicode 原样、sorted keys、compact separators、`allow_nan=false`。
- dataclass、mapping、tuple/list 使用稳定 JSON 形状。
- 字典插入顺序不影响 digest。
- SHA-256 使用 `sha256:<64 lowercase hex>`，覆盖完整 base result、pillars、base conventions、convention profile；同一函数可计算 derived result digest。
- canonical payload 检测 Windows drive path 和 POSIX absolute path，拒绝本地绝对路径。

## 8. Error Contracts

structured error 包含 `code`、`message`、`field_path`、`dependency`、`method_id`、`profile_id`。Schema 固定九个 R1 错误码：base invalid/unsupported/fingerprint mismatch、profile required/unsupported、dependency unresolved、field unavailable、capability disabled、output schema invalid。

## 9. Source Manifest and Independence Rules

manifest 为每项来源记录 source ID、标题、作者/机构、URL/书目、version/commit/edition、anchor、访问日、license note、independence group、verification status 和 capability。

五项 capability 均有至少两个 reviewed independence groups：传统原典组与现代实现组；NaYin/XunKong 另含独立《三命通会》组。`lunar-python` 来源锁定 commit `74c56657e02673d52f99d5afe8cfbd01b21cc1c7`。验证器不会把同一 independence group 重复计算为双源；未满足双源的 capability 不进入 `implementation_ready`。

这些来源只使合同/fixture 准备就绪，不代表映射 expected 已完成逐项交叉核验；静态 engine batch 仍须建立 272+ independent assertions，且项目输出不得充当 oracle。

## 10. Package Data Verification

五份 schema 位于 `src/mingli/contracts/schemas/`，顶层 `type` 均为 `object`。setuptools package-data 将 `schemas/*.json` 放入 wheel。测试与独立人工验证均从 wheel 建立临时隔离环境，在 source checkout 之外以 `importlib.resources` 成功读取全部 schema。

## 11. Tests

新增 10 个测试，覆盖 immutable model、canonical/hash 稳定性、Unicode、key order、base allowlist/shape/fingerprint、unknown profile、状态 schema、unresolved 不计通过的 manifest policy、非预测字段、绝对路径、来源独立组和 wheel 安装读取。完整 pytest 最终结果为 54 passed、1 skipped、2 subtests passed；unittest 为 45 tests OK、1 skipped。

首次把 unittest 与 pytest 并行运行时，二者同时执行 wheel build，导致 unittest 的临时 build 发生并发冲突并以 exit 1 结束；同一命令随后单独重跑 exit 0。该过程已如实保留，不将首次失败描述为通过。

## 12. Validation Commands and Exit Codes

| Command | Exit | Result |
|---|---:|---|
| `python -m compileall -q src tests` | 0 | pass |
| `python -m unittest discover -v` | 0 | 45 tests, OK, 1 skipped（顺序重跑） |
| `python -m pytest -q` | 0 | 54 passed, 1 skipped, 2 subtests passed |
| `python -m mingli.cli validate-spec spec` | 0 | pass |
| `python -m mingli.cli validate-rules spec/rules` | 0 | 36 rules, IDs unique |
| `python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl` | 0 | 40/40 + 24/24 |
| `python -m mingli.cli knowledge-validate knowledge` | 0 | pass |
| `python -m mingli.cli chart-validate --strict` | 0 | pass |
| `python -m mingli.cli chart-benchmark --independent-only` | 0 | 52 independent; 51 pass, 0 fail, 1 unresolved |
| `python -m build` | 0 | sdist + wheel built |
| isolated wheel install + five-schema read | 0 | all five returned top-level `object` |
| `git diff --check` | 0 | pass |
| protected path diff (`spec/`, `knowledge/`) | 0 | empty |

## 13. Known Limits

- 没有静态映射表或 derived engine；records 只是未来结果合同。
- source manifest 是来源基础，不是完成的 expected-value fixture；实现前仍需逐项双源核验与冲突表。
- 23:00 strict/explicit partial 已体现在结果和错误合同，但本批没有 derive orchestration，因此不执行依赖传播。
- schema 使用 implementation-owned 合同，不解决只读 `spec/` 中历史 schema 与 Phase 5 payload 的差异。

## 14. Explicit Non-Goals

未实现 chart-derive CLI、benchmark runner、藏干查询、十神计算、NaYin 查询、XunKong 计算、timeline、age、relations、twelve growth、interpretation、prediction、LLM、外部 API、数据库或网络运行时服务。

## 15. Readiness for Static Engine Batch

合同与来源基础达到 Batch 0/1 完成条件，但静态 engine 下一批只有在 272+ independent expected assertions 和逐项来源冲突记录完成后才能开始。当前 marker：

```text
PHASE_6_BATCH_0_1_COMPLETE
```

```yaml
spec_modified: false
knowledge_modified: false
phase5_output_modified: false
prediction_added: false
static_mapping_engine_implemented: false
original_p0_worktree_modified: false
```
