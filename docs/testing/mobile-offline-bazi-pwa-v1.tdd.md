# 手机离线八字 PWA v1 TDD 证据

> 状态：`LOCAL_CANDIDATE_VERIFIED`。证据 SHA 为 `7bcee5bade7cc043243a32e21415492245caf8e6`；报告提交会产生新的 Git SHA，最终 HEAD 与远端 CI/artifact 由 Draft PR、Issue #48 和最终交付记录。本文件不包含私人验收输入或完整结果。

## 来源、目标与边界

- 任务：`mqpmqp/mingli-agent` GitHub Issue #48。
- 分支：`codex/mobile-offline-bazi-pwa-v1-20260823`；基线：`debbcef633a3d32c87b8cb254c0958a9f7e0fe19`。
- 浏览器必须加载仓库 wheel 并调用 `mingli.bazi.DeterministicBaziEngine`，禁止近似 JavaScript 四柱算法。
- 不依赖 VPS、MCP、OpenAI、外部排盘/地图 API；不上传、持久化或缓存出生资料与结果。
- 未修改：`spec/`、`src/mingli/bazi.py`、冻结合同、四柱/真太阳时/节气/起运公式、Phase23、命理/紫微规则、Renderer、PR #47 VPS/Caddy。
- 私人验收只记录 `MANUAL_PRIVATE_ACCEPTANCE=PASS/FAIL`。

## 用户旅程

1. 手机用户首次联网下载固定静态资源，随后断网仍能加载并运行同一确定性 Python 引擎。
2. 用户填写历法、日期、分钟级时间、IANA 时区、性别、经纬度、真太阳时、闰月和 `fold`；坐标必须明确确认且修改后重新确认。
3. 用户查看引擎真实返回的时间、四柱、日主、起运、节气、版本、hash、warnings 与 `prediction_validity`，并主动复制或下载。
4. 表单变更立即失效旧结果；清空后异步复制或排盘均不得回写旧反馈/结果，DOM、Web Storage、IndexedDB 和 CacheStorage 不留用户资料。
5. 错误显示中文可操作提示；`SOLAR_TERM_UNCERTAIN` 必须显示 `REVIEW_REQUIRED` 且不显示确定四柱。
6. 维护者可用固定工具链复现 wheel、154 个 parity outcomes、100 次确定性、三档手机 E2E、离线与 CI artifact。

## RED / GREEN checkpoint

| 阶段 | Commit | RED/GREEN 证据 |
| --- | --- | --- |
| 最小 parity RED | `4fc7575` `test(pwa): add browser parity reproducer` | 移动 Chromium 要求加载仓库 wheel 并与 CPython 对比；目标运行时不存在，测试有效 RED。 |
| 最小 parity GREEN | `fe1b1a7` `feat(pwa): run deterministic engine in pinned Pyodide` | 固定 Pyodide/tzdata，构建 wheel；同一合成输入的完整结果一致。 |
| 完整 PWA RED | `5d6f280` `test(pwa): define offline mobile acceptance` | 154-case parity、100× determinism、UI、离线、隐私与可复现构建合同暴露缺失能力。 |
| bootstrap 完整性 RED | `d51f327` `test(pwa): reject tampered Pyodide bootstrap assets` | 篡改 asm.js 时旧实现进入执行并报语法错误，证明未在执行前验证。 |
| bootstrap 完整性 GREEN | `2088d9a` `feat(pwa): verify Pyodide bootstrap before execution` | module、asm.js、WASM、stdlib、lockfile 均先做 bytes/SHA 校验；4 个篡改用例与正常 PoC 通过。 |
| SW 更新 RED | `8e64188` `test(pwa): require activation of waiting service worker` | 点击“立即更新”未向 waiting worker 发送 `SKIP_WAITING`。 |
| SW 更新 GREEN | `1b0cfd9` `feat(pwa): activate waiting worker on update` | 发送 `SKIP_WAITING`，仅在 `controllerchange` 后 reload；focused E2E 通过。 |
| 交互状态 RED | `29b9d9b` `test(pwa): cover interaction state invalidation` | 三个独立 Chromium reproducer 分别得到：坐标确认仍 checked、表单变更后结果仍 visible、清空后旧复制反馈回写。 |
| 交互状态 GREEN | `1d45a10` `fix(pwa): invalidate stale interaction state` | 表单 input 清旧结果、坐标 input 撤销确认、clipboard feedback 使用 revision；同一 target `3 passed` 且 build PASS。 |
| SW 代际覆盖 | `68387b5` `test(pwa): cover service worker generation transitions` | 真实断言 `controllerchange` reload；预置旧 generation cache 后激活新 worker，最终只保留当前 build cache。 |
| 排盘清空竞态 RED | `923602d` `test(pwa): cover calculation clear race` | 真实 Chromium 微任务 reproducer 在清空后重新显示旧结果，`1 failed`。 |
| 排盘清空竞态 GREEN | `8acf452` `fix(pwa): ignore stale calculation results` | calculation revision 使更早 Promise 的结果/错误失效；同一 reproducer `1 passed`。 |
| CI 启动 RED | `1233288` `test(pwa): reject runner context before job start` | 远端 run `32785237461` 零 job 失败；本地合同测试因 job 级 `runner.temp` 命中而 `1 failed`。 |
| CI 启动 GREEN | `1518485` `fix(ci): defer runner temp until job starts` | 缓存路径下移到 runtime 构建 step；同一测试 `1 passed, 4 deselected`。 |

所有 checkpoint 均可从当前分支 HEAD 追溯，未 squash 或改写。

## 固定运行时与构建证据

| 项目 | 结果 |
| --- | --- |
| host CPython | `3.11.15` |
| Node / npm | `22.18.0` / `10.9.3` |
| Pyodide / embedded Python | `0.25.1` / `3.11.3` |
| tzdata | `2025.2` |
| Playwright / Vite | `1.55.1` / `7.3.6` |
| `ZoneInfo("Asia/Shanghai")` | `verified` |
| validation SHA | `7bcee5bade7cc043243a32e21415492245caf8e6` |
| app build ID | `90569ad1cc90cb513472` |
| wheel SHA-256 | `4306ec2dbb1b7320b7d68d65642839d392e6310bcf58909d4546a30069feba08` |
| first-load bytes | `13,947,405` |
| parity / determinism | `154/154`, failures `0`; `100/100` |
| measured timings | first load `141 ms`; first init `2722 ms`; first calc `142 ms`; second load `1843 ms`; second calc `88 ms` |
| local artifact | `mingli-mobile-pwa-7bcee5bade7cc043243a32e21415492245caf8e6.tar.gz` |
| local artifact SHA-256 | `4dc538bb57dc16ae7d14289f05ca3fa98086c66b60dbfd16f5a4f6c7bed76ed8`，两次独立打包一致 |

## 测试规格与证据映射

| # | 保证 | 测试 | 结果 |
| --- | --- | --- | --- |
| 1 | 固定依赖与下载 SHA | `tests/test_pwa_runtime_build.py` | PASS |
| 2 | corpus 至少 100 且覆盖成功/错误边界 | runtime-build test + generated reference | PASS，154 cases |
| 3 | manifest 路径、排序、字节数、SHA 和 wheel/tzdata binding | Python + Vite + runtime | PASS |
| 4 | wheel 使用 Git 派生 `SOURCE_DATE_EPOCH` | runtime-build test | PASS |
| 5 | Pyodide bootstrap 未验证字节不得执行 | `parity.poc.spec.ts` | PASS，4 tamper cases |
| 6 | 表单、闰月、坐标、时区、fold、中文错误 | unit + E2E | PASS |
| 7 | 坐标修改必须重新确认 | `e2e.spec.ts` | RED→GREEN |
| 8 | 表单修改失效旧结果 | `e2e.spec.ts` | RED→GREEN |
| 9 | 清空后 pending clipboard 不得回写 | `e2e.spec.ts` | RED→GREEN |
| 10 | 清空后 pending calculation 不得回写结果/错误 | `e2e.spec.ts` | RED→GREEN |
| 11 | 结果字段、复制、下载、prompt、清空 | presentation unit + E2E | PASS |
| 12 | 版本不一致失败关闭，waiting worker 被激活并重载 | version unit + E2E | PASS |
| 13 | 旧 build cache 删除、当前 cache 保留 | `offline.spec.ts` | PASS |
| 14 | CPython↔Pyodide PoC 完整相等 | `npm run test:parity` | PASS |
| 15 | 154 outcomes 完全相等 | `parity.spec.ts` | PASS，154/154 |
| 16 | 100× pillars/luck/hash 一致 | `parity.spec.ts` | PASS，100/100 |
| 17 | 360×800、390×844、430×932 | `npm run test:e2e` | PASS |
| 18 | 首次在线、第二次断网加载与离线排盘 | `npm run test:offline` | PASS |
| 19 | 无上传/持久化/用户数据缓存 | E2E request/storage/cache audit | PASS |
| 20 | `SOLAR_TERM_UNCERTAIN` 显示 `REVIEW_REQUIRED` 且无四柱 | `e2e.spec.ts` | PASS |
| 21 | CI 干净重建、测试、确定性 tar.gz + SHA 收据，不部署 Pages | `.github/workflows/pwa.yml` | 静态审计 PASS；远端 run 在 push 后确认 |
| 22 | `runner.temp` 仅在 runner 已分配的 step 中求值 | `test_workflow_defers_runner_temp_until_a_step_is_running` | RED→GREEN |

## 实际命令与结果

| 命令 | 结果 |
| --- | --- |
| `python -m pytest -q tests/test_pwa_runtime_build.py tests/test_bazi_engine.py` | `10 passed, 2 subtests passed` |
| `python -m pytest -q tests/test_pwa_runtime_build.py -k workflow_defers_runner_temp` | RED：`1 failed, 4 deselected`；GREEN：`1 passed, 4 deselected` |
| CI 启动修复后重跑同一 focused suite | `11 passed, 2 subtests passed` |
| `test-fast --timeout-seconds 300 ... -- -q` | `404 passed, 1 skipped, 151 deselected, 2 warnings, 16 subtests passed` |
| 完整 `python -m pytest` | `555 passed, 1 skipped, 31 subtests passed, 2 warnings`；validation SHA 上实际运行 `1138.63s` |
| `python -m compileall -q src scripts` | PASS |
| `python -m build` | PASS，sdist + wheel |
| `python -m pip check` | PASS |
| `npm audit --audit-level=high` | `0 vulnerabilities` |
| `python -m pip_audit` | `No known vulnerabilities`；本地 `mingli-agent` 按工具规则跳过 |
| `npm test` | `39 passed` |
| `npm run test:coverage` | statements/lines `96.38%`; branches `87.03%`; functions `100%` |
| `npm run build` | PASS |
| `npm run test:parity` | `8 passed`; 154/154; 100/100 |
| `npm run test:e2e` | `17 passed, 22 intentional project skips` |
| `npm run test:offline` | `3 passed` |
| CI 参数本地重复打包 | artifact SHA-256 两次一致，determinism PASS |
| 私人本地验收 | `MANUAL_PRIVATE_ACCEPTANCE=PASS` |

## 解释与剩余边界

- 移动 E2E 的 22 个 skip 是显式项目矩阵策略：运行时/状态测试仅在 canonical 390 项目执行；三个视口都执行 shell 与真实结果旅程，不是禁用测试。
- 完整 pytest、Python focused 与 `test-fast` 均在 validation SHA 上实际通过；保护范围审计同时确认 Python 核心未改。
- 首次远端 PWA run 在 job 创建前失败；新增合同测试复现并把 `runner.temp` 下移到 step，最终远端结论另行记录。
- `controllerchange` 可早于 activate 事件 `waitUntil` 清理完成；旧 cache 测试有界轮询最终 CacheStorage 状态。
- parity 证明同一确定性实现工程一致，不等于命理预测准确率；`prediction_validity=not_evaluated` 保留。
- 离线缓存仍可能被浏览器或操作系统回收；固定 tzdata 未来修订需要新构建和重新 parity。
- `web/pwa/public/runtime/` 与 `web/pwa/dist/` 是忽略生成物；GitHub Actions 不含 Pages 权限或部署步骤。
- 远端 CI、artifact 名称/SHA、push、Draft PR 和 Issue 更新必须在最终 HEAD 上完成后在外部交付记录中填写。
