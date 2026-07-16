# MingLi V2.0 产品闭环与 Training Loop 实现报告

日期：2026-07-15
分支：`codex/v2-product-training-loop`
起始提交：`e99aa2a5d04c4cdbac6e027e2f95bffdbbcb454b`

## 1. 实现结论

当前工程状态：

- `PRODUCT_CAPABILITY_READY`
- `COMMERCIAL_VALIDATION_PENDING`
- `development_runtime_allowed=true`
- `production_commercial_allowed=false`
- 兼容旧状态：`PRODUCT_RELEASE_HOLD`

上述状态由 Phase 24 实际输出证明。它只说明 V2.0 产品开发链和 Training Loop 已闭环，不证明预测准确率，也不构成商业发布授权。

## 2. 已实现

- 新增 consent/privacy 门控的产品 runtime compatibility layer，实际调用既有 Phase 23，而不是复制或 mock 核心算法。
- 每次运行只读校验 Knowledge OS 并记录内容 manifest hash；Phase 16 rule_set_hash、Phase 20 renderer 版本和 Phase 23 engine 版本进入统一 envelope。
- 统一 input/output JSON Schema；输出包含 run/version/time/confidence/reason/limitations/reality evidence/八段 sections/trace 和 structured errors。
- 可靠计算缺失时 fail closed 为 `blocked`，低置信或 unresolved 为 `degraded`；不由文本模型补全结果。
- Reality Evidence 继续使用 Phase 18 claim/scope 级 hard override；Yuan renderer 继续只呈现结构化结果。
- 新增 TrainingCase、AnalysisRun、UserFeedback、OutcomeObservation、RuleReviewCandidate、TrainingIteration 六类 schema。
- 新增仓库外 JSON/JSONL store、HMAC case_id 校验、PII 扫描、重复记录保护、tombstone、派生记录失效和非 PII audit。
- Training Feedback 固定 `counts_toward_accuracy=false`；普通 outcome 不自动进入商业验证。
- 由明确纠正/缺失上下文生成的规则候选固定为低置信 `pending_human_review`、`applied_to_rules=false`。
- 顶层 CLI 新增 `mingli training run|feedback|outcome|show|review|candidates|withdraw`，统一 JSON 输出和稳定退出码。
- Phase 24 schema 升级到 `release-candidate-assessment@0.6`，增加产品能力/商业验证双门字段，同时保留旧 release 字段。

## 3. 明确未实现

- 没有收集、生成、导入或修改任何真实案例。
- 没有运行真实案例准确率评估，没有生成准确率数字。
- 没有解除事前 claim 冻结、outcome 时间边界、独立评分、泄漏检测、可复现数据集和商业风险审批责任。
- 没有让候选规则自动进入 Knowledge OS 或正式 Rules。
- 没有引入数据库、网络服务、LLM 推理补全或第二套 CLI。
- 没有 push、PR 或 merge。

## 4. 修改文件

产品代码：

- `src/mingli/product_runtime.py`
- `src/mingli/training.py`
- `src/mingli/training_cli.py`
- `src/mingli/product_readiness.py`
- `src/mingli/cli.py`
- `src/mingli/phase24.py`

契约：

- `product_runtime_input.schema.json`
- `product_runtime_envelope.schema.json`
- `training_case.schema.json`
- `analysis_run.schema.json`
- `user_feedback.schema.json`
- `outcome_observation.schema.json`
- `rule_review_candidate.schema.json`
- `training_iteration.schema.json`

测试：

- `tests/test_product_training_loop.py`
- `tests/test_phase24_release_candidate.py`
- `tests/test_derived_contracts.py`

文档：

- `V2_PRODUCT_TRAINING_LOOP_PREFLIGHT.md`
- `TRAINING_LOOP_GUIDE.md`
- `V2_PRODUCT_READINESS.md`
- `COMMERCIAL_VALIDATION_GATE.md`
- `DATA_PRIVACY_AND_CONSENT.md`
- `RELEASE_GATE_MIGRATION.md`
- 本报告

`spec/` 未修改。

## 5. 测试与验证证据

### TDD 与专项

- 红灯：`python -m pytest -q tests/test_product_training_loop.py` 初次收集失败，缺少 `mingli.product_readiness`。
- 中间红灯：新增 Knowledge trace/iteration 测试为 2 failed、14 passed；实现后转绿。
- 最终专项：`python -m pytest -q tests/test_product_training_loop.py` -> `16 passed in 22.39s`。
- Phase 23/24/Training compatibility 组合 -> `30 passed in 72.49s`（迁移后 Phase 24 又由 real-case gate 覆盖）。
- wheel schema 失败项修复后定点复跑 -> `1 passed in 39.71s`。

### 完整 gate

- 误调用：`python -m mingli.test_gates fast --timeout-seconds 600 -- -q` -> exit 1；参数被 REMAINDER 传给 pytest，报 `unrecognized arguments: --timeout-seconds`。这是命令调用错误，不是测试失败。
- 正确 fast：`python -m mingli.test_gates --timeout-seconds 600 fast -- -q` -> exit 0；`177 passed, 1 skipped, 90 deselected, 16 subtests passed in 256.31s`。
- real-case 合同门：`python -m mingli.test_gates --timeout-seconds 900 real_case -- -q` -> exit 0；`58 passed, 210 deselected in 51.17s`。该门只证明合同/隐私/合成 dry-run，不是准确率。
- benchmark 首轮：exit 1；`31 passed, 1 failed, 236 deselected, 15 subtests passed in 1631.92s`。唯一失败是 wheel 测试仍硬编码 13 schemas，实际合法新增后为 21。
- benchmark 最终复跑：`python -m mingli.test_gates --timeout-seconds 1800 benchmark -- -q` -> exit 0；`32 passed, 236 deselected, 15 subtests passed in 1420.81s`。

### 覆盖率

安装到既有质量虚拟环境的验证工具：`pytest-cov 7.1.0` / `coverage 7.15.1`，未写入项目依赖。

命令：`python -m pytest -q tests/test_product_training_loop.py --cov=mingli.product_runtime --cov=mingli.training --cov=mingli.training_cli --cov=mingli.product_readiness --cov-report=term-missing`

- product_readiness：100%
- product_runtime：82%
- training：91%
- training_cli：71%
- 新增模块合计：451 statements，65 missed，**86%**

### 编译与构建

- `python -m compileall -q src tests` -> exit 0。
- `python -m py_compile`（product runtime/training/CLI/readiness/Phase 24）-> exit 0。
- `python -m build --wheel --outdir <TEMP>` -> exit 0；生成 `mingli_agent-2.0.0-py3-none-any.whl`，316,962 bytes；21 个 schemas 被打包。

### 静态检查

- 新增产品/训练代码与测试 Ruff -> `All checks passed`。
- 整仓 Ruff -> 395 个历史 finding；在起始提交独立 worktree 实测也是 395，delta=0。
- 新增产品/训练代码与测试 Pyright -> 0 errors。
- 整仓 Pyright -> 356 个历史 error；在起始提交独立 worktree 实测也是 356，delta=0。
- `git diff --check` -> exit 0。

### 依赖审计

均使用 `pip-audit`，未自动升级依赖：

- 项目 runtime resolution：8 dependencies，0 vulnerabilities，0 skipped。
- development requirements：7 dependencies，0 vulnerabilities，0 skipped。
- build-system `setuptools>=68`：pip-audit 返回 exit 0 / no known vulnerabilities，但 JSON 中为 0 个 auditable dependency；因此不能把它表述为已检查到具体 setuptools 版本，只能记录工具未报告漏洞。

### 隐私与密钥

- `python scripts/check_validation_privacy.py` -> `{"failures": [], "passed": true}`。
- repository secret regex scan -> 无匹配（`rg` exit 1 表示零匹配）。
- 未发现真实个人资料、原始身份泄漏、硬编码 key、salt、private key 或 validation/training store。
- 测试中的手机号样式仅是合成 PII 拒绝 sentinel，不是现实个人资料，也不会被产品/训练存储接受。

## 6. 当前阻塞项与下一步

产品开发闭环没有未关闭工程 blocker。商业化仍被以下条件阻塞：授权真实案例集、事前冻结 claims、outcome 时间边界、独立评分、泄漏检测、可复现 benchmark、准确率/失效模式报告和商业风险审批。

下一步应先由有权限的数据流程在 Git 外准备 consent 完整、HMAC 去标识的真实数据，再走既有 validation freeze/review/authorization；不要用 Training Feedback 替代该流程。

最终标记：`MINGLI_V2_PRODUCT_TRAINING_LOOP_COMPLETE`
