# 手机离线八字 PWA

该 PWA 在浏览器内通过固定版本的 Pyodide 运行仓库构建出的 `mingli-agent` Python wheel，实际调用 `mingli.bazi.DeterministicBaziEngine`。它没有另写一套 JavaScript 四柱算法，也不依赖 VPS、MCP、OpenAI API 或第三方排盘 API。

## 使用前须知

- 第一次使用必须联网，让浏览器下载应用外壳、Pyodide、时区数据和当前仓库 wheel。当前设计的首次静态运行时约为 14 MB；准确字节数以本次构建生成的 `web/pwa/public/runtime/runtime-manifest.json` 中 `first_load_bytes` 为准。
- 只有页面明确显示“离线可用”后，才可以断网。此后同一版本可以从 Service Worker 的静态缓存启动并在本地排盘。
- 浏览器或操作系统可能清理站点缓存。无痕模式、清除站点数据、空间不足或版本升级后，可能需要再次联网完成缓存。
- 出生资料和排盘结果只存在于当前页面内存中，不会上传，也不会默认写入 `localStorage`、`sessionStorage` 或 IndexedDB。Service Worker 只缓存静态文件。
- 首次下载静态资源时，静态托管方仍可能像普通网站一样记录 IP、User-Agent 等访问日志；请求中不包含表单出生资料或排盘结果。

页面会显示“本地计算，出生资料未上传”。复制或下载结果只会在用户主动点击相应按钮后发生。

## 输入与坐标

输入页包含性别、历法、出生日期和分钟级时间、IANA 时区、出生地备注、经纬度、真太阳时、农历闰月选项，以及用于处理重复民用时间的高级 `fold` 选项。

第一版不包含可靠的地点数据库或地理编码服务。因此：

- 经度和纬度必须手工填写并由用户确认；应用不会猜测坐标。
- 应用不会把出生地备注发送给地图或地理编码 API。
- 启用真太阳时时必须提供有效经度；经度范围为 `-180` 至 `180`，纬度范围为 `-90` 至 `90`。
- “是否闰月”只在农历输入时适用。
- 时区应使用 `Asia/Shanghai`、`America/New_York` 这类 IANA 名称。`fold` 仅用于确有重复本地时间的时区场景，不能修复不存在的本地时间。

坐标会直接影响真太阳时修正。无法确认坐标时，应关闭真太阳时或先从可信来源核对，不要用城市名猜测。

## 安装与离线使用

PWA 安装要求安全上下文，通常是 HTTPS；本机开发的 `localhost` 或 `127.0.0.1` 也可用于测试。

1. 保持联网并打开应用。
2. 等待 Python 运行时初始化完成，确认页面显示“离线可用”。
3. 使用浏览器菜单中的“安装应用”或“添加到主屏幕”。不同浏览器的菜单名称可能不同。
4. 完成一次测试排盘后再断网重载，确认该设备没有清理缓存。

如果页面提示有新版本，请先恢复联网并刷新。不要在升级未完成时继续依赖旧页面。

## 版本绑定与失败关闭

每次构建会把应用脚本、Git commit、Python wheel SHA-256、Pyodide 版本和应用构建 ID 绑定在一起。页面发现应用脚本、运行时清单或 wheel 不属于同一构建时，会停止计算并要求联网刷新，不会静默混用“新 JavaScript + 旧 wheel”。

以下情况也会失败关闭：

- 固定下载文件的 SHA-256 与 `web/pwa/runtime-lock.json` 不一致；
- Python wheel、Pyodide 或 tzdata 无法加载；
- 输入落在节气计算不确定区间，返回 `SOLAR_TERM_UNCERTAIN`；页面必须显示 `REVIEW_REQUIRED`，不得继续给出确定四柱；
- 日期、时间、历法、性别、坐标、时区、闰月、`fold` 或支持年份不合法。

刷新仍不能解决版本错误时，可清除该站点的缓存和 Service Worker，然后联网重新打开。清除站点数据不会删除应用保存的出生记录，因为应用本身不保存这类记录，但会移除离线静态资源。

## 本地开发

固定工具链记录在 `web/pwa/runtime-lock.json` 和 `web/pwa/package-lock.json`：

| 组件 | 固定版本 |
| --- | --- |
| CPython | 3.11.15 |
| Node.js | 22.18.0 |
| npm | 10.9.3 |
| Pyodide | 0.25.1（内含 CPython 3.11.3） |
| tzdata | 2025.2 |
| Playwright | 1.55.1 |
| Vite | 7.3.6 |

在仓库根目录安装 Python 依赖并生成浏览器运行时：

```bash
python -m pip install -e ".[dev]"
python scripts/build_pwa_runtime.py
```

构建脚本会下载锁定的 Pyodide 和 tzdata 文件，并在解包或复制前校验 SHA-256。下载缓存默认位于系统临时目录；可以用 `MINGLI_PWA_RUNTIME_CACHE` 指向独立构建缓存。生成的 `web/pwa/public/runtime/` 体积较大且不提交 Git。

然后安装前端依赖并启动本地服务：

```bash
cd web/pwa
npm ci
npm run dev
```

打开 `http://127.0.0.1:4173/`。如果开发机上的 Python 命令不是 `python`，运行浏览器 parity 前把 `PWA_PYTHON` 设置为正确的 CPython 3.11.15 可执行文件。

## 构建与测试

Python 定点、编译、打包和依赖一致性检查：

```bash
python -m pytest -q tests/test_pwa_runtime_build.py tests/test_bazi_engine.py
python -m compileall -q src scripts
python -m build
python -m pip check
python scripts/build_pwa_runtime.py
```

前端单元、覆盖率、构建、浏览器 parity、移动端和离线测试：

```bash
cd web/pwa
npm ci
npx playwright install chromium
npm test
npm run test:coverage
npm run build
npm run test:parity
npm run test:e2e
npm run test:offline
```

`test:parity` 比较 CPython 参考结果与 Chromium 中同一 Python 引擎的完整 canonical 结果；它证明工程实现一致，不代表命理预测准确率。移动端测试覆盖仓库配置的 360×800、390×844 和 430×932 视口，离线测试检查第二次加载、离线计算以及静态缓存隐私边界。

独立 GitHub Actions 工作流 `.github/workflows/pwa.yml` 会执行上述门禁，把 `web/pwa/dist/` 打包为 `mingli-mobile-pwa-<git-sha>.tar.gz`，同时生成同名 `.sha256` 收据并上传二者。工作流没有 Pages 权限或部署步骤，不会启用 GitHub Pages。

## 功能边界与剩余风险

- PWA 只提供确定性排盘字段、复制和 JSON 导出，不计算或补写格局、喜忌、流年、事件预测或科学有效性结论。
- `prediction_validity=not_evaluated` 必须原样保留；浏览器与 CPython 一致不等于现实预测有效。
- 固定 tzdata 只代表该构建携带的时区数据库版本。历史时区规则未来修订时，需要发布新构建并重新执行 parity。
- 节气边界不确定、超出引擎支持年份或无法判定的民用时间会被拒绝，需要人工复核或更正输入。
- 离线能力依赖浏览器的 Service Worker 与 Cache Storage 支持及缓存保留策略，不能保证操作系统永不回收缓存。
- 本仓库只生成静态构建工件，不负责公开托管，也没有启用 GitHub Pages。
