# MingLi 手机离线八字 PWA v1 实现报告

> `REPORT_STATUS=LOCAL_CANDIDATE_VERIFIED`
>
> 本报告记录 2026-08-25 在本地候选 SHA `7bcee5bade7cc043243a32e21415492245caf8e6` 上取得的证据。报告文件随后被提交会产生新的 Git SHA，因此最终分支 HEAD、远端 CI run 与 artifact 收据以 Draft PR、Issue #48 和最终交付字段为准；不得把自引用 SHA 伪造为同一个值。本报告不包含私人验收输入或完整结果。

## 实现摘要

PWA 使用固定 Pyodide `0.25.1` 加载本仓库构建的 wheel，在手机 Chromium 中直接调用 `mingli.bazi.DeterministicBaziEngine`。没有重写 JavaScript 四柱算法，也没有使用 VPS、MCP、OpenAI、外部排盘/地图 API、analytics 或出生资料服务端存储。

浏览器在执行前验证 Pyodide module、asm.js、WASM、stdlib、lockfile、tzdata 和仓库 wheel 的路径、字节数与 SHA-256；应用脚本、Git SHA、wheel SHA、Pyodide、tzdata 和 app build ID 必须一致。Service Worker 只缓存同源静态 GET 资源，更新时通过 `SKIP_WAITING`、`controllerchange` 和 build-generation cache 清理完成切换。

点击路径独立审计发现并修复：修改经纬度后旧坐标确认未撤销、表单修改后旧结果仍可导出、延迟剪贴板 promise 可在清空后回写反馈、较早的排盘 promise 可在清空后回写结果。四个真实 Chromium 回归均先 RED 后 GREEN。

## 本地候选构建收据

| 字段 | 值 |
| --- | --- |
| validation Git SHA | `7bcee5bade7cc043243a32e21415492245caf8e6` |
| app build ID | `90569ad1cc90cb513472` |
| wheel SHA-256 | `4306ec2dbb1b7320b7d68d65642839d392e6310bcf58909d4546a30069feba08` |
| first-load bytes | `13,947,405` |
| Pyodide / embedded Python | `0.25.1` / `3.11.3` |
| host Python / Node | `3.11.15` / `22.18.0` |
| tzdata / Playwright / Vite | `2025.2` / `1.55.1` / `7.3.6` |
| parity | `154/154`, failures `0` |
| determinism | `100/100` |
| performance | first load `141 ms`; first init `2722 ms`; first calc `142 ms`; second load `1843 ms`; second calc `88 ms` |
| local artifact | `mingli-mobile-pwa-7bcee5bade7cc043243a32e21415492245caf8e6.tar.gz` |
| local artifact SHA-256 | `4dc538bb57dc16ae7d14289f05ca3fa98086c66b60dbfd16f5a4f6c7bed76ed8` |
| local artifact determinism | PASS，两次独立打包 SHA-256 完全一致 |

## 验证结果

- Python focused：`10 passed, 2 subtests passed`。
- `test-fast`：`404 passed, 1 skipped, 151 deselected, 2 warnings, 16 subtests passed`。
- 完整 pytest：`555 passed, 1 skipped, 31 subtests passed, 2 warnings`，在 validation SHA 上实际运行 `1138.63s`。
- `compileall`、sdist/wheel build、`pip check`：PASS。
- 依赖审计：`npm audit` 为 `0 vulnerabilities`；`pip-audit` 为 `No known vulnerabilities`（本地 `mingli-agent` 因不在 PyPI 按工具规则跳过）。
- 前端 unit：`39/39`；coverage statements/lines `96.38%`、branches `87.03%`、functions `100%`。
- parity：`8/8`，含 4 个 bootstrap 篡改失败关闭、PoC、ZoneInfo、154-case parity 与 100× determinism。
- 移动 E2E：`17 passed, 22 intentional project skips`；360×800、390×844、430×932 均执行 shell 与真实排盘旅程。
- offline：`3/3`；installability、断网重载/排盘、请求/Web Storage/IndexedDB/CacheStorage 隐私、旧 cache 代际清理均通过。
- `MANUAL_PRIVATE_ACCEPTANCE=PASS`。

## Issue #48 交付字段（本地候选）

~~~text
VERDICT=PASS_LOCAL_CANDIDATE
ROOT_CAUSE_OR_IMPLEMENTATION_SUMMARY=固定 Pyodide 加载仓库 wheel 并直接运行 DeterministicBaziEngine；完整性、版本绑定、离线、移动与隐私门禁已在本地候选通过

REPO_ROOT=D:\Backup\Documents\命理师V2.0
BRANCH=codex/mobile-offline-bazi-pwa-v1-20260823
BASE_SHA=debbcef633a3d32c87b8cb254c0958a9f7e0fe19
FINAL_SHA=由最终提交和远端 CI 记录；本报告验证 SHA 为 7bcee5bade7cc043243a32e21415492245caf8e6
WORKTREE_CLEAN=NO_REPORT_COMMIT_PENDING_AT_EVIDENCE_CAPTURE

FILES_CHANGED=.gitignore,README.md,scripts/build_pwa_runtime.py,tests/test_pwa_runtime_build.py,web/pwa/**,.github/workflows/pwa.yml,docs/mobile-pwa.md,docs/testing/mobile-offline-bazi-pwa-v1.tdd.md,MINGLI_MOBILE_PWA_V1_REPORT.md
FILES_NOT_CHANGED=spec/**,src/mingli/bazi.py,frozen contracts,Phase23,命理规则,紫微规则,Renderer,PR #47 VPS/Caddy logic
SPEC_CHANGED=NO
FROZEN_CONTRACTS_CHANGED=NO
BAZI_CORE_ALGORITHM_CHANGED=NO

PYTHON_VERSION=3.11.15
NODE_VERSION=22.18.0
PYODIDE_VERSION=0.25.1
TZDATA_VERSION=2025.2
WHEEL_SHA256=4306ec2dbb1b7320b7d68d65642839d392e6310bcf58909d4546a30069feba08
BUILD_SHA=90569ad1cc90cb513472

PYODIDE_IMPORT=PASS
ZONEINFO_ASIA_SHANGHAI=PASS
CPYTHON_BROWSER_PARITY=PASS
PARITY_CASES=154
PARITY_FAILURES=0
DETERMINISM_100X=PASS

PWA_BUILD=PASS
PWA_INSTALLABLE=PASS
PWA_STANDALONE=PASS
PWA_FIRST_LOAD=PASS
PWA_SECOND_LOAD=PASS
PWA_OFFLINE_LOAD=PASS
PWA_OFFLINE_CALC=PASS
SERVICE_WORKER_PRIVACY=PASS
NO_USER_DATA_UPLOAD=PASS

MOBILE_360x800=PASS
MOBILE_390x844=PASS
MOBILE_430x932=PASS

PYTHON_TESTS=PASS_10_PLUS_2_SUBTESTS
FRONTEND_TESTS=PASS_39_OF_39
PARITY_TESTS=PASS_8_OF_8_154_CASES
PLAYWRIGHT_TESTS=PASS_17_WITH_22_INTENTIONAL_PROJECT_SKIPS
OFFLINE_TESTS=PASS_3_OF_3
FAST_TESTS=PASS_404_SKIP_1_DESELECTED_151_SUBTESTS_16
FULL_TESTS=PASS_555_SKIP_1_SUBTESTS_31_AT_VALIDATION_SHA
COMPILEALL=PASS
BUILD=PASS_PYTHON_AND_PWA
PIP_CHECK=PASS
DIFF_CHECK=PASS_LOCAL_CANDIDATE

MANUAL_PRIVATE_ACCEPTANCE=PASS

CI_WORKFLOW=.github/workflows/pwa.yml
CI_STATUS=NOT_RUN_PRE_PUSH
ARTIFACT_NAME=GENERATED_BY_CI_AFTER_PUSH
ARTIFACT_SHA256=GENERATED_BY_CI_AFTER_PUSH

COMMIT=IMPLEMENTATION_SHA_7bcee5bade7cc043243a32e21415492245caf8e6; FINAL_REPORT_COMMIT_FOLLOWS
PUSHED=NO_PRE_RELEASE
PR=NOT_CREATED_PRE_RELEASE
PR_DRAFT=YES_REQUIRED
MERGED=NO
GITHUB_PAGES_DEPLOYED=NO

BLOCKERS=NONE_LOCAL
RESIDUAL_RISKS=浏览器或操作系统可回收离线缓存；固定 tzdata 未来可能修订；parity 不代表命理预测有效性；远端 CI 和 artifact 收据需在最终 HEAD 上确认
NEXT_ACTION=提交报告、最终 HEAD 重建复验、推送并创建 Draft PR，更新 Issue #48 后监控 CI 与远端 artifact
~~~

## 不变范围与隐私边界

- `spec/`、冻结合同、`src/mingli/bazi.py`、Phase23、命理/紫微规则、Renderer 和 PR #47 部署逻辑均未修改。
- `web/pwa/public/runtime/` 与 `web/pwa/dist/` 是忽略的生成物，不提交大型 Pyodide 二进制。
- Service Worker 只缓存静态资源；真实浏览器审计确认没有出生资料上传、Web Storage/IndexedDB 持久化或用户输入/结果 CacheStorage 残留。
- 私人验收只保留 `MANUAL_PRIVATE_ACCEPTANCE=PASS`，本报告不包含输入或完整结果。
- `.github/workflows/pwa.yml` 只有 `contents: read`，没有 Pages、部署或 `id-token` 权限。
- CPython↔Pyodide parity 只证明同一确定性工程实现一致，不代表命理预测准确率或科学有效性。
