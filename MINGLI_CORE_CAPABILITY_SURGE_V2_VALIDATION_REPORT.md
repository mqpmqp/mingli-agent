# MINGLI Core Capability Surge V2 统一验证报告

代码 checkpoint：`97a50149519f84099451a8c30e2dc54310c8fce6`  
验证日期：2026-07-17  
结果：本地工程门禁通过；远端 Draft PR CI 待创建后确认。  
Release Hold：`ACTIVE`

## 测试与合同

| 门禁 | 结果 |
| --- | --- |
| schema / spec / rule validation | PASS；spec、36 rule IDs、全部打包 schema 有效 |
| knowledge / chart validation | PASS；knowledge inventory 可读，strict independent chart benchmark 通过 |
| frozen contracts | PASS；baseline `00eeaad...`，78 checked，0 violations |
| V2 focused | PASS；修复后 105 passed；含 Bazi、Ziwei、Real Case、统一 runtime |
| contract/schema selector | PASS；81 passed（checkpoint `6f32471...`），随后 final full regression 通过 |
| golden selector | PASS；1 passed（checkpoint `6f32471...`），随后 final full regression 通过 |
| property-style invariant selector | PASS；44 passed（checkpoint `6f32471...`），随后 final full regression 通过 |
| mutation / false-pass selector | PASS；40 passed（checkpoint `6f32471...`），随后 final full regression 通过 |
| fast gate | PASS；343 passed、1 skipped、150 deselected，265.49s |
| benchmark gate | PASS；38 passed、456 deselected，920.97s |
| real-case gate | PASS；112 passed、382 deselected，46.22s |
| full pytest | PASS；493 passed、1 skipped，1691.89s |

唯一 skip 为 Windows 缺少 symlink privilege 时的既有平台条件测试：`SourceRegistryTests::test_symlinks_are_rejected_including_outside_repository`。本轮 diff 没有新增 skip、skipif 或 xfail。

## 静态、构建与安装

| 门禁 | 结果 |
| --- | --- |
| compileall | PASS；`src tests scripts` |
| changed-scope Ruff | PASS；All checks passed |
| changed-scope Pyright | PASS；0 errors、0 warnings |
| full-repository Ruff probe | 非配置门禁；复现 main 继承的 394 个历史问题，集中在旧 spec 脚本/测试；未做无关清理 |
| wheel | PASS；`mingli_agent-2.0.0-py3-none-any.whl` |
| sdist | PASS；`mingli_agent-2.0.0.tar.gz`，canonicalized metadata |
| archive privacy scan | PASS |
| isolated wheel install | PASS；仅从外部临时 dist 安装 `[api]` extra |
| installed-wheel schema smoke | PASS |
| HTTP smoke | PASS；capabilities 200、invalid request 400、Hold/validity 边界正确 |
| MCP smoke | PASS；initialize/tools-list，统一工具只读且非 destructive |

仓库没有配置全仓 Ruff 或 type-check gate；本轮仍对所有新增/修改 Python 执行了增量 Ruff 与 Pyright。增量 Pyright 首轮发现 26 个收窄问题，修复提交 `97a5014` 后为 0。

## 安全与卫生

| 门禁 | 结果 |
| --- | --- |
| `pip-audit . --strict` | PASS；No known vulnerabilities found |
| `git diff --check` | PASS |
| credential scan | PASS；0 files |
| local path scan | PASS；0 files |
| fail-open scan | PASS；0 suspicious files |
| disabled-test diff scan | PASS；0 matches |
| generated artifact tracked/status scan | PASS；0 tracked artifacts，normal Git status clean |
| validation privacy | PASS；source 与 wheel/sdist archives 均无 failure |

构建工具会在工作树生成被 Git 忽略的标准 cache/egg-info。它们不进入提交、wheel/sdist 或 PR diff；normal Git status 保持 clean。外部临时构建产物未复制回仓库。

## 准确率与发布边界

- `real_case_count=0`。
- `accuracy_metrics=null`。
- `product_accuracy_claim_allowed=false`。
- `prediction_validity=not_evaluated`。
- `product_release_status=PRODUCT_RELEASE_HOLD`。

因此，本报告只证明工程合同、失败边界与可复现构建通过，不证明命理预测准确率。
