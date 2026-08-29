# 命理师 V2.0 完整升级实际变更报告

报告日期：2026-08-29
分支：`codex/mingli-v2-paid-delivery-upgrade-20260829`
核心 GREEN checkpoint：`ddd1774`

## WHAT：完成内容

- 修复并验证 Windows、WSL、Git、PyPI 和 npm 网络路径；本地代理端点为 `127.0.0.1:22593`；
- 完成先行只读审计，并形成 `MINGLI_V2_FULL_UPGRADE_AUDIT.md`；
- 新增统一 `CaseInput`、出生/图片四柱、六爻输入、现实约束、证据质量、复盘点和自动降级合同；
- 新增命盘、解释、事件、行动四维置信度与领域现实反证；
- 新增九类专题 production 安全规则包；
- 新增完整 `AdviceRule` 合同、九类建议目录与财务/健康/风水 fail-closed 逻辑；
- 新增 Comment、Private、Paid-699 三档确定性 Renderer；
- 新增 699 九项合同、续问短合同和称骨显式 opt-in；
- 新增六状态规则治理与 production-only 选择；
- 新增九类 forward-test 结果、到期门禁、反馈来源门禁和确定性结算收据；
- 新增 RED/GREEN、渲染、安全语言、降级、建议匹配、draft 隔离、到期、续问和称骨禁止测试；
- 补齐付费合同、建议治理、置信度与反证、评测政策和 TDD 证据文档。

## SCOPE：变更范围

核心代码：

- `src/mingli/delivery_contracts.py`
- `src/mingli/rule_governance.py`
- `src/mingli/paid_delivery.py`
- `src/mingli/forward_evaluation.py`

测试：

- `tests/test_paid_delivery_upgrade.py`
- `tests/test_rule_and_advice_governance_v2.py`
- `tests/test_forward_evaluation_policy_v2.py`

文档：

- `MINGLI_V2_FULL_UPGRADE_AUDIT.md`
- `MINGLI_V2_FULL_UPGRADE_SPEC.md`
- `PAID_DELIVERY_CONTRACT.md`
- `METAPHYSICAL_ADVICE_GOVERNANCE.md`
- `CONFIDENCE_AND_COUNTEREVIDENCE.md`
- `EVALUATION_AND_FORWARD_TEST_POLICY.md`
- `MINGLI_V2_FULL_UPGRADE_TDD_EVIDENCE_REPORT.md`
- 本报告和 README 对应入口说明。

明确未修改：

- `spec/`、`knowledge/`；
- Phase 19、Phase 20、Phase 23 的旧兼容行为；
- Hermes、Telegram、真实 Vision/OCR、PWA 产品逻辑；
- 任何交易项目或交易依赖；
- `.env`、密钥、令牌、真实用户资料、验证私库；
- 生产环境、远端分支、PR 和部署配置。

## HOW：已运行命令

网络门禁：

```powershell
curl.exe -L -sS -o NUL -w '%{http_code}' https://github.com/
curl.exe -L -sS -o NUL -w '%{http_code}' https://pypi.org/simple/
curl.exe -L -sS -o NUL -w '%{http_code}' https://registry.npmjs.org/
wsl.exe -e bash -lc "curl -L -sS -o /dev/null -w 'github=%{http_code} tls=%{ssl_verify_result}\n' https://github.com/; curl -L -sS -o /dev/null -w 'pypi=%{http_code} tls=%{ssl_verify_result}\n' https://pypi.org/simple/; curl -L -sS -o /dev/null -w 'npm=%{http_code} tls=%{ssl_verify_result}\n' https://registry.npmjs.org/"
git ls-remote --exit-code origin HEAD
npm ping --registry=https://registry.npmjs.org/
```

TDD 与覆盖率：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests\test_paid_delivery_upgrade.py `
  tests\test_rule_and_advice_governance_v2.py `
  tests\test_forward_evaluation_policy_v2.py

.\.venv\Scripts\python.exe -m coverage run --branch -m pytest -q `
  -p no:cacheprovider `
  tests\test_paid_delivery_upgrade.py `
  tests\test_rule_and_advice_governance_v2.py `
  tests\test_forward_evaluation_policy_v2.py
.\.venv\Scripts\python.exe -m coverage report `
  --include='src/mingli/delivery_contracts.py,src/mingli/rule_governance.py,src/mingli/paid_delivery.py,src/mingli/forward_evaluation.py'
```

语法与 Git：

```powershell
.\.venv\Scripts\python.exe -m py_compile <四个新模块>
git diff --check
git status --short --branch
```

所有下列验收命令均在文档写入后实际执行；失败项先修复，再重跑到终态。

最终验收实际追加执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
test-fast --timeout-seconds 300 -- -q -p no:cacheprovider
test-real-case --timeout-seconds 600 -- -q -p no:cacheprovider
test-benchmark --timeout-seconds 3600 -- -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m compileall -q src tests scripts
.\.venv\Scripts\python.exe -m build
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m mingli.cli validate-spec spec
.\.venv\Scripts\python.exe -m mingli.cli validate-rules spec/rules
.\.venv\Scripts\python.exe -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl
.\.venv\Scripts\python.exe -m mingli.cli chart-validate --strict
.\.venv\Scripts\python.exe -m mingli.cli chart-benchmark --independent-only
```

PWA 使用本机 Node `22.21.1` / npm `10.9.4`，并在 parity/E2E 中显式设置 `PWA_PYTHON` 为仓库 Python 3.11：

```powershell
npm ci
npm test
npm run test:coverage
npm run build
npm run test:parity
npm run test:e2e
npm run test:offline
npm audit --audit-level=high
```

Python 安全审计工具安装在系统临时隔离 venv；项目 `.venv` 的 pip/setuptools 工具链按审计结果升级后，重跑 `pip-audit --path .\.venv\Lib\site-packages`、新增测试、build 和 wheel smoke。三类 test gate 的实际验收还写入了仓库外临时 JUnit 文件；上方省略该输出路径，不影响选择器和超时参数。

## RESULT：当前真实结果

| 门禁 | 当前结果 |
|---|---|
| Windows GitHub/PyPI/npm HTTPS | PASS，三项 HTTP 200 |
| WSL GitHub/PyPI/npm HTTPS | PASS，三项 HTTP 200 且 TLS verify result 0 |
| Git 远端只读访问 | PASS，`ls-remote origin HEAD` 返回对象 |
| npm registry | PASS，`npm ping` 返回 PONG |
| 原有相关审计基线 | PASS，`162 passed, 9 subtests passed in 149.07s` |
| 原有相关回归复跑 | PASS，`162 passed, 9 subtests passed in 117.97s` |
| 新测试 RED | PASS，三个预期新模块缺失错误 |
| 新测试 GREEN | PASS，`34 passed in 0.39s` |
| 新模块 branch coverage | PASS，总计 `80%` |
| 新模块 `py_compile` | PASS |
| 新增三阶段独立验收 | PASS：`12 passed`、`16 passed`、`6 passed` |
| 全量 pytest | PASS：`593 passed, 1 skipped, 2 warnings, 31 subtests passed in 1613.24s` |
| fast gate | PASS：`441 passed, 1 skipped, 152 deselected, 2 warnings, 16 subtests passed in 260.42s` |
| real-case gate | PASS：`112 passed, 482 deselected, 2 warnings in 38.70s` |
| benchmark gate | PASS：`40 passed, 554 deselected, 2 warnings, 15 subtests passed in 1292.12s` |
| `compileall` | PASS |
| sdist / wheel build | PASS；工具链修复后再次 PASS |
| `pip check` | PASS；工具链修复后再次 PASS |
| spec / rules / static benchmark | PASS；静态 benchmark 40/40 |
| strict chart validation | PASS |
| independent chart benchmark | PASS：51 passed、1 unresolved source conflict、0 failed |
| installed wheel smoke | PASS；默认无称骨字段，缺资料主动低置信 |
| Python lint / type-check | NOT_CONFIGURED；仓库没有对应命令 |
| PWA `npm ci` / audit | PASS；0 vulnerabilities；Node 精确版本有 `EBADENGINE` warning |
| PWA unit / coverage | PASS：46 tests；statements 96.75%、branches 87.69% |
| PWA `tsc --noEmit` + Vite build | PASS |
| PWA parity | 首次 7 pass/1 fail，原因为系统 Python 未安装 package；绑定 `PWA_PYTHON` 后 PASS：8 passed |
| PWA Chromium E2E | PASS：24 passed、36 intentional skips |
| PWA offline | PASS：5 passed；manifest 与 Chromium acceptance PASS |
| iOS / Android 实机安装 | NOT_RUN |
| npm audit | PASS：0 vulnerabilities |
| pip-audit | 首次 FAIL：pip/setuptools 工具链漏洞；升级后 PASS：No known vulnerabilities；本地非 PyPI 包不可查询 |

## BLOCKERS：当前阻塞

- 六爻无可靠引擎，只能验证输入并降级；
- 图片四柱缺出生元数据时不能推导起运、真太阳时或时间线；
- 当前没有授权真实 forward-test 数据，不能形成准确率结论；
- PWA 不消费新付费路径，本次只做兼容回归；
- Hermes/Telegram、实机移动端、真实图片和生产 E2E 均不在本地实现授权范围。
- PWA `package.json` 写死 Node `22.18.0`，本机可用的是 `22.21.1`；所有自动化通过，但 npm 保留精确版本 warning。
- 全量 Python 测试保留两条既有第三方 warning：Starlette `httpx` deprecation 与 Pydantic settings forward-reference warning。

## HEAD / WORKTREE

- 核心实现 checkpoint：`ddd1774`；最终文档与验收提交 SHA 以最终交付消息为准。
- 本报告创建时工作树包含待提交文档变更；不能提前写成干净。
