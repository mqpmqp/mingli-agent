# 手机离线八字 PWA v1 TDD 证据

> 状态：`POST_REVIEW_LOCAL_CANDIDATE_VERIFIED`。人工审查主体代码证据 SHA 为 `2e775306bcad25cda82331cb4e4ecc225ce51104`；图标 LFS/Core 边界修复 GREEN SHA 为 `89ad22d5bd9aec10a86101ca560e7d908fcaf4dc`。文档提交会产生新的 Git SHA，最终 HEAD、CI 与 artifact 绑定值只在 push 后写入 Draft PR #49、Issue #48 和最终交付记录。本文件不包含私人验收输入或完整结果。

## 来源、目标与边界

- 来源：`mqpmqp/mingli-agent` Issue #48 与 Draft PR #49 人工审查评论。
- 分支：`codex/mobile-offline-bazi-pwa-v1-20260823`；base：`debbcef633a3d32c87b8cb254c0958a9f7e0fe19`；审查基线：`347f5d3b92a6f28e6058b9749600c182be04cc71`。
- 浏览器加载当前提交构建的 wheel 并调用 `mingli.bazi.DeterministicBaziEngine`；禁止近似 JavaScript 历法/四柱算法。
- 不依赖 VPS、MCP、OpenAI、外部排盘/地图 API；不上传、持久化或缓存出生资料与结果。
- 未修改 `spec/**`、`src/mingli/bazi.py`、冻结合同、四柱/真太阳时/节气/起运公式、Phase23、命理/紫微规则、Renderer、PR #47 VPS/Caddy。
- `MANUAL_PRIVATE_ACCEPTANCE=NOT_RUN_IN_THIS_REVIEW`。

## 用户旅程

1. 阳历用户继续使用原生日期控件；农历用户用独立年/月/日控件输入 `2023`、`2`、`29` 等不具公历语义的日期。
2. 前端只校验农历年 `1901–2099`、月 `1–12`、日 `1–30`；具体月份、日期与闰月是否存在由 Python 引擎权威判断。
3. 用户只用键盘完成阳历或农历核心流程；错误后焦点、alert 与字段 ARIA 状态可恢复，清空后回到首个输入。
4. 冷浏览器首次加载每个固定 Runtime 资产最多一次真实网络传输，且首次完成后可离线，SHA 与五项版本绑定不削弱。
5. 全字段纯合成隐私值不得进入网络 URL/query/headers/body、Web Storage、IndexedDB、CacheStorage 或清空后的 DOM。
6. 维护者可复现 154-case CPython↔Pyodide parity、100× determinism、三档手机 E2E、离线、安装清单和 artifact。

## RED / GREEN checkpoint

| 范围 | RED commit 与真实失败 | GREEN commit 与保证 |
| --- | --- | --- |
| 最小 parity | `4fc7575`：移动 Chromium 需要仓库 wheel，但 Runtime 不存在，测试有效 RED。 | `fe1b1a7`：固定 Pyodide/tzdata 并运行同一 Python 引擎；合成输入与 CPython 完整一致。 |
| 完整 PWA | `5d6f280`：154 parity、100× determinism、UI、离线、隐私与可复现构建合同暴露缺失能力。 | 后续线性提交逐项闭合；没有 squash 或改写。 |
| bootstrap 完整性 | `d51f327`：篡改 asm.js 时旧实现进入执行并报语法错误。 | `2088d9a`：module、asm.js、WASM、stdlib、lockfile 均先做 bytes/SHA 校验。 |
| SW 更新 | `8e64188`：点击更新没有向 waiting worker 发送 `SKIP_WAITING`。 | `1b0cfd9`：发送消息并仅在 `controllerchange` 后 reload。 |
| 交互状态 | `29b9d9b`：坐标确认未撤销、旧结果仍可导出、清空后旧复制反馈回写。 | `1d45a10`：input 失效旧结果、坐标变更撤销确认、clipboard 使用 revision。 |
| SW 代际 | `68387b5` 增加真实 `controllerchange` 与旧 generation cache 回归。 | 当前实现只保留当前 app build cache。 |
| 排盘清空竞态 | `923602d`：清空后较早排盘 Promise 重新显示旧结果，`1 failed`。 | `8acf452`：calculation revision 使较早结果/错误失效，同一测试 `1 passed`。 |
| CI 启动 | `1233288`：远端 run `32785237461` 零 job；本地合同因 job 级 `runner.temp` 命中，`1 failed, 4 deselected`。 | `1518485`：缓存路径下移到 runner 已分配的 step；`1 passed, 4 deselected`。 |
| F1 农历输入 | `44bc3e9`：Vitest 不接受独立农历字段，Chromium 切农历后仍显示 Gregorian `type=date`，合法闰二月二十九无法输入。 | `3c15f1a`：独立数字控件转换为既有 `birth_date` 合同；真实 UI 的闰二月二十九、非法三十日与普通非闰月旅程通过。 |
| F2 农历错误映射 | `1aa621d`：`INVALID_LUNAR_DATE` 落入通用提示，缺少月份、日期、闰月指引。 | `e23825c`：安全中文提示覆盖并不回显内部 code/stack。 |
| F2 集合防漂移 | `462b15c`：AST 提取发现 `INVALID_INPUT`、`INVALID_LUNAR_DATE`、`INTERNAL_SOLAR_TERM` 未映射。 | `e23825c`：核心 `_fail` 字符串集合与前端只读映射集合相等。 |
| F4 键盘/a11y | `cab8779`：键盘提交后焦点未到错误摘要，摘要不可聚焦，字段没有 `aria-invalid`/`aria-describedby`。 | `159c7b4`：错误摘要可聚焦且为 alert；字段错误关联可设置和撤销；阳历/农历键盘旅程通过。 |
| F5 冷启动传输 | `a83afdf`：冷启动测量观察到页面与 SW 对同一 Runtime 资产产生重复真实传输。 | `bd1f443`：先取得 SW control，再加载 Runtime；独立 server/CDP 收据中重复真实传输为 0。 |
| F3/F6 安装与隐私 | `b4a04a`：收紧图标内容/尺寸、分层安装收据与全字段网络/CacheStorage 哨兵，旧实现不满足门禁。 | `c7d33df` 增加标准 PNG 图标；`f7c7f98` 用基线 cache 摘要消除静态资源误报并证明用户输入未改变 cache。 |
| 失败注入隔离 | `b8487b9`、`2e77530`：禁用 SW cache 干扰，确保 Runtime 篡改与 manifest retry 测试命中预期失败路径。 | focused、全量 E2E 与 offline 均保持 GREEN。 |
| F3 CI 图标交付 | 最终候选 push run `32844730423` 与 PR run `32844735580` 的 offline step 收到以 `version ` 开头的 Git LFS pointer 而非 PNG；`6bb8fd2` 新增 Git index blob 合同并得到 `1 failed, 6 deselected`。 | `6204187` 在生成的 LFS 规则块外为三个小图标添加精确 override，并把 index 转为普通 PNG blob；同一测试 `1 passed, 6 deselected`，focused suite `13 passed, 2 subtests passed`。 |
| F3 LFS policy 集成 | `6204187` 的手工 override 触发知识资产生成合同，fast gate 得到同源 `5 failed, 402 passed`；`8e01af1` 增加 focused 生成合同并得到 `1 failed, 7 deselected`。 | `41b69db` 把精确图标例外纳入 `asset_policy.yaml` 并由既有生成器渲染；新合同与原 5 个失败 `6 passed`，focused `14 passed, 2 subtests passed`，fast `408 passed, 1 skipped, 151 deselected, 16 subtests passed`。 |
| F3 LFS/Core 边界 | Core workflow 对 `origin/main...HEAD -- knowledge` 要求零差异，因此根策略扩展不能作为最终方案；`aa2736b` 将合同改为目录级例外，真实 RED 为缺少 `web/pwa/public/icons/.gitattributes` 的 `FileNotFoundError`。 | `89ad22d` 将 `*.png -filter -diff -merge -text` 下沉到图标目录，并恢复根生成文件、`asset_policy.yaml` 与 `mingli.knowledge`；同一合同连同 `test_knowledge_os.py` 为 `9 passed, 1 skipped`，`knowledge/**` 相对 base 恢复零差异。 |

所有 checkpoint 都位于当前分支从审查基线向前的线性历史中。

## 整改代码候选绑定证据

| 项目 | 结果 |
| --- | --- |
| host CPython | `3.11.15` |
| local Node / npm | `22.23.1` / `10.9.8`；CI 固定 `22.18.0` / `10.9.3` |
| Pyodide / embedded Python | `0.25.1` / `3.11.3` |
| tzdata | `2025.2` |
| Playwright / Vite | `1.55.1` / `7.3.6` |
| post-review code evidence SHA | `2e775306bcad25cda82331cb4e4ecc225ce51104` |
| app build ID | `d27a1f76a943b609f37a` |
| wheel SHA-256 | `a9725253b86f8e4f4397825d57b2bd40aa8fbf1440916531bdf20c58fa4c4199` |
| first-load asset bytes | `13,947,405` |
| first-load transfer bytes | `13,953,953` |
| duplicate runtime network fetches | `0` |
| cold-start environment | fresh Playwright Chromium context；无既有 SW/CacheStorage；CDP 清站点数据与 browser cache；`Cache-Control: no-store` 独立 loopback server；server socket 字节收据与页面请求关联 |
| parity / determinism | `154/154`；`100/100` |
| install receipts | manifest `PASS`；Chromium `PASS`；iOS/Android physical install `NOT_RUN` |

以上绑定值属于整改代码候选。报告提交后的最终绑定值必须由最终 HEAD 构建、CI 与 artifact 重新取得，不能预填为同一个 SHA。

## 测试规格与证据映射

| # | 保证 | 测试 | 结果 |
| --- | --- | --- | --- |
| 1 | 农历控件没有 Gregorian date 语义，合法闰二月二十九真实 UI 成功 | `form.test.ts` + `e2e.spec.ts` | PASS |
| 2 | 结构合法的农历三十日提交到引擎，由 `INVALID_LUNAR_DATE` 安全拒绝且无旧四柱 | `presentation.test.ts` + `e2e.spec.ts` | PASS |
| 3 | 核心 `_fail` error code 与前端映射集合一致 | `test_pwa_runtime_build.py` | PASS |
| 4 | 真实 Tab/Arrow/Space/Enter 完成阳历和农历旅程 | `e2e.spec.ts` keyboard group | PASS，3 tests |
| 5 | manifest 内容、PNG 类型/实际尺寸与 Chromium 接受 | `offline.spec.ts` | PASS |
| 6 | 冷启动固定 Runtime 资产无重复真实网络传输 | `offline.spec.ts` isolated cold-start test | PASS，duplicate `0` |
| 7 | 所有敏感字段不进入网络/storage/cache/清空后 DOM | `offline.spec.ts` all-field privacy test | PASS |
| 8 | manifest 路径、排序、bytes/SHA 与 wheel/tzdata binding | Python + Vite + Runtime | PASS |
| 9 | Pyodide bootstrap 未验证字节不得执行 | `parity.poc.spec.ts` | PASS，4 tamper cases |
| 10 | 154 outcomes 与 100× 确定性 | `parity.spec.ts` | PASS |
| 11 | 360×800、390×844、430×932 | `npm run test:e2e` | PASS |
| 12 | 首次在线、第二次断网加载与离线排盘 | `npm run test:offline` | PASS |
| 13 | `SOLAR_TERM_UNCERTAIN` 显示 `REVIEW_REQUIRED` 且无确定四柱 | `e2e.spec.ts` | PASS |
| 14 | workflow 干净重建并上传普通 CI artifact，不部署 Pages | `.github/workflows/pwa.yml` + Python contract test | PASS |

## 实际命令与结果

| 命令 | 结果 |
| --- | --- |
| `python -m pytest -q tests/test_pwa_runtime_build.py tests/test_bazi_engine.py` | 默认 pytest temp ACL 首次 `2 setup errors`；使用任务独占 `--basetemp` 后 `12 passed, 2 subtests passed` |
| CI 图标 blob 修复后同一 focused suite | `13 passed, 2 subtests passed` |
| LFS policy 集成后同一 focused suite | `14 passed, 2 subtests passed` |
| 目录级 LFS/Core 边界合同 | RED：`1 failed`（缺少嵌套 `.gitattributes`）；GREEN：`9 passed, 1 skipped`（同一合同 + `test_knowledge_os.py`） |
| `python -m mingli.test_gates --timeout-seconds 1200 fast -- -q --basetemp=<任务独占目录>` | `408 passed, 1 skipped, 151 deselected, 1 warning, 16 subtests passed` |
| `python -m pytest` | `557 passed, 1 skipped, 2 warnings`，`1483.30s` |
| `python -m compileall -q src scripts` | PASS |
| `python -m build` | PASS，sdist + wheel |
| `python -m pip check` | PASS |
| `npm ci` | PASS；本地 Node/npm 非 CI 固定版本，出现 engine warning |
| `npm audit --audit-level=high` | `0 vulnerabilities` |
| `npm test` | `46 passed` |
| `npm run test:coverage` | statements/lines `96.75%`; branches `87.69%`; functions `100%` |
| `npm run build` | PASS |
| `npm run test:parity` | `8 passed`; `154/154`; `100/100` |
| `npm run test:e2e` | `24 passed, 36 intentional project skips` |
| `npm run test:offline` | `5 passed` |
| `git diff --check` | PASS |
| 私人资料人工验收 | `NOT_RUN_IN_THIS_REVIEW` |

## 解释与剩余边界

- project skip 是显式 Playwright 矩阵策略：需要完整 Runtime 的行为只在 canonical 390 项目执行，三个视口仍执行共同移动旅程；没有为本轮失败新增 skip。
- `FIRST_LOAD_ASSET_BYTES` 是固定 Runtime 静态资产 body 总数；`FIRST_LOAD_TRANSFER_BYTES` 是独立 server/CDP 实测 encoded transfer 总数，两者不混写。
- `PWA_MANIFEST_INSTALLABILITY=PASS` 与 `CHROMIUM_PWA_ACCEPTANCE=PASS` 不等于 iOS/Android 实机安装；两项 physical install 均为 `NOT_RUN`。
- 完整 pytest、focused、fast、前端与浏览器门禁已在整改代码候选执行；文档提交后的最终 HEAD 会重新构建并复验。
- parity 证明同一确定性实现工程一致，不代表命理预测准确率；`prediction_validity=not_evaluated` 保留。
- 离线缓存可能被浏览器或操作系统回收；固定 tzdata 未来修订需要新构建和重新 parity。
- `web/pwa/public/runtime/**` 与 `web/pwa/dist/**` 是忽略生成物；workflow 不含 Pages 权限或部署步骤。
