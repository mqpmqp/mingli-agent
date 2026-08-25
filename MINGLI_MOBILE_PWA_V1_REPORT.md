# MingLi 手机离线八字 PWA v1 实现报告

> `REPORT_STATUS=POST_REVIEW_LOCAL_CANDIDATE_VERIFIED`
>
> 本报告记录人工审查整改代码提交 `2e775306bcad25cda82331cb4e4ecc225ce51104` 上已经取得的本地证据。报告提交本身会生成新的 Git SHA，因此最终分支 HEAD、app build ID、wheel SHA、CI run 与 artifact 摘要只在最终 push 后写入 Draft PR #49、Issue #48 收据和交付回复，避免伪造自引用 SHA。本轮没有执行私人资料人工验收。

## 实现摘要

PWA 使用固定 Pyodide `0.25.1` 加载本仓库构建的 wheel，并在浏览器内直接调用 `mingli.bazi.DeterministicBaziEngine`。前端没有重写农历、四柱、节气、真太阳时或起运算法，也没有使用 VPS、MCP、OpenAI、外部排盘/地图 API、analytics 或出生资料服务端存储。

本轮人工审查整改闭合六项：

- F1：阳历保留原生 `type=date`；农历改为独立年/月/日数字控件，结构校验后仍提交既有 `birth_date: YYYY-MM-DD` 合同，具体农历合法性由 Python 引擎判断。
- F2：前端中文提示覆盖 `src/mingli/bazi.py` 当前全部 `_fail("ERROR_CODE", ...)` 集合，并由 AST 集合合同防漂移；未知错误继续 fail closed。
- F3：提供标准 192×192、512×512 与 180×180 PNG 图标；自动化只声明 manifest/Chromium 接受证据，不冒充 iOS/Android 实机安装。
- F4：真实键盘旅程覆盖阳历、农历、结果操作和清空；错误摘要可聚焦，字段使用 `aria-invalid` 与 `aria-describedby`，修正后撤销过期关联。
- F5：先用独立 loopback server、CDP 和服务端字节收据测量冷启动，再改为 Service Worker 先完成控制后加载 Runtime；固定 Runtime 资产首次真实网络传输重复数为 0，完整性与版本绑定未削弱。
- F6：纯合成全字段隐私哨兵检查 URL、query、可读 headers、body、Web Storage、IndexedDB、CacheStorage 和清空后的 DOM；无 mutation、`/api` 或跨域 HTTP 请求。

浏览器在执行前验证 Pyodide module、asm.js、WASM、stdlib、lockfile、tzdata 和仓库 wheel 的路径、字节数与 SHA-256。应用脚本、Git SHA、wheel SHA、Pyodide、tzdata 和 app build ID 必须一致。Service Worker 只缓存同源、scope 内、非 API 的 GET 静态资源。

## 整改代码候选收据

| 字段 | 值 |
| --- | --- |
| review baseline | `347f5d3b92a6f28e6058b9749600c182be04cc71` |
| post-review code evidence SHA | `2e775306bcad25cda82331cb4e4ecc225ce51104` |
| app build ID | `d27a1f76a943b609f37a` |
| wheel SHA-256 | `a9725253b86f8e4f4397825d57b2bd40aa8fbf1440916531bdf20c58fa4c4199` |
| first-load asset bytes | `13,947,405` |
| first-load transfer bytes | `13,953,953` |
| duplicate runtime network fetches | `0` |
| Pyodide / embedded Python | `0.25.1` / `3.11.3` |
| host Python | `3.11.15` |
| local Node / npm | `22.23.1` / `10.9.8`（本地出现 engine warning；CI 固定 `22.18.0` / `10.9.3`） |
| tzdata / Playwright / Vite | `2025.2` / `1.55.1` / `7.3.6` |
| parity | `154/154`，failures `0` |
| determinism | `100/100` |
| installability evidence | `PWA_MANIFEST_INSTALLABILITY=PASS`; `CHROMIUM_PWA_ACCEPTANCE=PASS` |
| physical install evidence | `IOS_PHYSICAL_INSTALL=NOT_RUN`; `ANDROID_PHYSICAL_INSTALL=NOT_RUN` |
| manual private acceptance | `NOT_RUN_IN_THIS_REVIEW` |

这些值绑定整改代码候选，不冒充报告提交后的最终 HEAD。最终值由最终 HEAD 的 CI 和 artifact 独立复算后外部登记。

## 本地验证结果

- Python focused：`12 passed, 2 subtests passed`。Windows 默认 pytest 临时目录 ACL 首次导致 2 个 setup errors；改用任务独占 `--basetemp` 后同一测试目标通过。
- `test-fast`：`406 passed, 1 skipped, 151 deselected, 16 subtests passed`。
- 完整 pytest：`557 passed, 1 skipped, 2 warnings`，`1483.30s`。
- `compileall`、sdist/wheel build、`pip check`：PASS。
- 前端 unit：`46/46`。
- coverage：statements/lines `96.75%`、branches `87.69%`、functions `100%`。
- parity：`8/8`，含 `154/154` outcomes 与 `100/100` determinism。
- Playwright E2E：`24 passed, 36 intentional project skips`；360×800、390×844、430×932 三档移动视口继续执行。
- offline：`5/5`，含 manifest/Chromium 接受、cold-start 网络测量、全字段隐私、断网重载/排盘与 cache generation。
- `npm audit --audit-level=high`：`0 vulnerabilities`。
- `git diff --check`：PASS。

最终文档提交后会在其 HEAD 上重新构建 Runtime/PWA 并重跑项目要求的本地门禁；远端 CI 和 artifact 收据不在本文件中预填。

## TDD checkpoint

完整 RED/GREEN 映射见 `docs/testing/mobile-offline-bazi-pwa-v1.tdd.md`。本轮关键链路：

- F1：`44bc3e9` RED → `3c15f1a` GREEN。
- F2：`1aa621d`、`462b15c` RED → `e23825c` GREEN。
- F4：`cab8779` RED → `159c7b4` GREEN。
- F5：`a83afdf` RED → `bd1f443` GREEN。
- F3/F6：`b4a04a` 收紧门禁 → `c7d33df`、`f7c7f98` GREEN。
- 隔离回归：`b8487b9`、`2e77530` 防止 Service Worker cache 干扰 Runtime 篡改与 retry 失败注入。

## 最终交付字段策略

最终 push 后，PR/Issue/交付回复必须同时登记：

- final Git SHA、app build ID、wheel SHA、Pyodide、tzdata 与 154-case 版本绑定；
- `FIRST_LOAD_ASSET_BYTES`、真实 `FIRST_LOAD_TRANSFER_BYTES`、`DUPLICATE_RUNTIME_NETWORK_FETCHES` 和测量环境；
- push、pull_request 与 Core Runtime 三组成功 CI run；
- GitHub artifact ZIP digest 与内部 `mingli-mobile-pwa-<FINAL_SHA>.tar.gz` SHA-256，两个摘要分开记录；
- `PWA_MANIFEST_INSTALLABILITY=PASS`、`CHROMIUM_PWA_ACCEPTANCE=PASS`、`IOS_PHYSICAL_INSTALL=NOT_RUN`、`ANDROID_PHYSICAL_INSTALL=NOT_RUN`。

不得再写无条件 `PWA_INSTALLABLE=PASS`，也不得把未执行的私人资料验收写成 PASS。

## 不变范围与剩余风险

- `spec/**`、冻结合同、`src/mingli/bazi.py`、Phase23、命理/紫微规则、Renderer 和 PR #47 VPS/Caddy 均未修改。
- `web/pwa/public/runtime/**` 与 `web/pwa/dist/**` 是忽略生成物，不提交大型 Pyodide 二进制。
- `.github/workflows/pwa.yml` 只有 `contents: read`，没有 Pages、deploy 或 `id-token` 权限。
- Chromium 自动化证明 manifest/浏览器接受与离线行为；没有 iOS Safari 或 Android 实机安装收据。
- 首次使用需要在线下载约 13.95 MB；浏览器或操作系统仍可能回收离线 cache。
- 固定 tzdata 未来修订需要新构建与重新 parity；工程 parity 不代表命理预测准确率，`prediction_validity=not_evaluated` 保留。
