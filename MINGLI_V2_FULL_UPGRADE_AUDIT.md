# 命理师 V2.0 付费交付与评测体系升级审计

审计日期：2026-08-29
审计方式：先只读检查仓库、配置、源代码、测试与公开规范；未读取 `.env`、私密评测揭盲文件或真实用户数据。
阶段结论：`PASS_WITH_IMPLEMENTATION_GAPS`。仓库身份与基线可锁定，相关基线测试通过，可以进入独立分支上的 TDD 实现；下列缺口不得被描述为已经具备。

## 1. 仓库身份与工作边界

- 真实仓库根：`D:/Backup/Documents/命理师V2.0`
- 审计起始分支：`codex/mobile-offline-bazi-pwa-v1-20260823`
- 审计起始 HEAD：`5b389b069f012f13a898de7661111ebb9e28161d`
- 起始上游：`origin/codex/mobile-offline-bazi-pwa-v1-20260823`，当时 `+0/-0`
- 远端标识：`https://github.com/mqpmqp/mingli-agent.git`；本次未 fetch、push 或调用 GitHub API
- 工作树：审计前干净；仅有一个登记 worktree
- 独立实施分支：`codex/mingli-v2-paid-delivery-upgrade-20260829`，从上述精确 HEAD 创建
- 当前分支相对本地 `origin/main` 为 41 个提交领先、0 个提交落后；差异为已存在的手机离线 PWA 工作
- 仓库内未发现 Binance、futures、trading 或交易项目路径；仓库外交易项目不在本任务作用域

保护边界：

- `spec/` 是只读来源与合同基线，AGENTS.md 明确禁止改写
- `knowledge/` 由 CI 单独执行零差异保护，本次不修改
- `spec/**/private/`、真实验证 store、揭盲资料、`.env`、密钥、令牌和生产数据不读取、不提交
- 既有 `web/pwa/` 候选、Hermes/Telegram、生产服务、部署配置与仓库外项目不做无关改动
- 不部署、不推送、不创建 PR、不修改生产环境

## 2. 技术栈、包管理器与真实命令

### Python 核心

- 单体 Python package：`mingli-agent==2.0.0`
- Python 要求：`>=3.11`
- 本地项目虚拟环境：CPython `3.11.15`
- 系统默认 Python：`3.13.5`，不作为本任务验收解释器
- 构建后端：`setuptools.build_meta`
- 运行依赖：`jsonschema`、`PyYAML`、`referencing`，Windows 额外 `tzdata`
- 开发依赖：`pytest`、`build`；API 可选依赖为 `mcp[cli]`
- 仓库没有 uv/Poetry/Pipenv 锁文件；Python 包安装使用 pip

仓库和 CI 已声明的主要命令：

```powershell
python -m pip install -e ".[dev,api]"
python -m compileall src tests scripts
test-fast --timeout-seconds 300 --junitxml artifacts/test-fast.xml -- -q
test-real-case --timeout-seconds 600 --junitxml artifacts/test-real-case.xml -- -q
test-benchmark --timeout-seconds 3600 --junitxml artifacts/test-benchmark.xml -- -q
python -m pytest -q
python -m build
python -m pip check
python -m mingli.cli validate-spec spec
python -m mingli.cli validate-rules spec/rules
python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl
python -m mingli.cli chart-validate --strict
python -m mingli.cli chart-benchmark --independent-only
git diff --check
```

当前 Python 配置没有 Ruff、Flake8、Mypy 或 Pyright 命令，也没有独立 lint/type-check 门禁。最终报告必须把这些项目如实记为“仓库未配置”，不能伪报通过；可执行 `compileall`、pytest、构建与既有 CLI 验证作为真实门禁。

### 手机 PWA

- 包管理器：`npm@10.9.3`，锁文件为 `web/pwa/package-lock.json`
- Node：`22.18.0`
- TypeScript `5.9.2`、Vite `7.3.6`、Vitest `3.2.7`、Playwright `1.55.1`
- `npm run build` 内含 `tsc --noEmit`，因此同时承担前端 type-check 与 build
- 没有独立前端 lint 脚本

真实前端命令：

```powershell
cd web/pwa
npm ci
npm test
npm run test:coverage
npm run build
npm run test:parity
npm run test:e2e
npm run test:offline
```

## 3. 当前输入合同

当前输入分散在多套合同中，尚无统一 `CaseInput`：

- `mingli.models.ChartInput`：性别、历法、出生日期、时间、地点、时区、真太阳时开关、来源
- `spec/schemas/birth_input.schema.json`：受保护的 BirthInput 规范；要求性别、历法、日期、时间、国家与城市
- `product_runtime_input.schema.json`：假名 case_id、时间、同意、宽松 `chart_input`、anchor_year、现实、证据、建议码、场景
- `confirmed_pillar_runtime.py`：只接受明确 `confirmed` 的四柱，严格区分 `image_confirmed` 与 `text_confirmed` provenance
- `intake/image_chart.py`：图片候选四柱必须经用户确认后才生成 `confirmed_pillars` handoff

缺口：

- 没有统一的 `CaseInput`、`BirthInput` Python 合同、`DivinationInput`、`QuestionIntent`、`PaidTier`
- 没有 `RealityConstraints`、`EvidenceQuality`、四维 `ConfidenceProfile`、`ReviewCheckpoint`
- 图片确认链存在，但尚未纳入统一输入合同
- 六爻六次结果、起卦时间、地点、目标事件没有运行时输入合同
- 感情现实状态字段分散在 `RealityContext`、Phase 17、Phase 18，考试成绩、岗位和招录目标没有统一结构
- 资料缺失主要表现为异常或局部低置信，并非统一、可审计的自动降级收据

## 4. 确定性引擎现状

### 八字、真太阳时、起运与大运

- `DeterministicBaziEngine` 支持 1901—2099 年、公历/农历、IANA 或固定偏移时区
- 年界采用立春，月界采用十二节；节气 15 分钟不确定区间 fail closed
- 真太阳时由经度修正与均时差组成；启用时必须提供经度
- 日界当前固定为校正后当地时间 00:00，不实现早晚子时分流
- 起运顺逆按年干阴阳与性别决定，起运显示值使用相邻节气间隔除以 3
- Phase 7 使用 UTC 整数微秒和 365.2425 日回归年生成精确起运锚点、大运区间与流年区间
- 成功排盘均保留 `prediction_validity=not_evaluated`，排盘成功不等于预测有效

### 图片四柱

- 未确认图片只生成候选和确认提示
- 已确认四柱可进入静态 Runtime，支持结构、强弱、格局、调候/喜忌相关已审核层
- 因缺少出生元数据，精确起运、当前大运、真太阳时和称骨被明确列为 unsupported

### 六爻

- 没有六爻排盘或断卦引擎
- 仓库只有知识来源清单和“没有六爻盘不得调用六神”的方法边界
- 因无可靠实现，本升级只能建立严格输入合同和显式不可用/降级路径，不能伪造六爻算法或精确结论

## 5. RenderIntent、三档模式与当前默认行为

`mingli.render_intent.RenderIntent` 当前有四个展示意图：

- `full_reading`
- `focused_question`
- `follow_up`
- `comment`

分类器在没有“完整/全盘”、评论或续问信号时，默认返回 `focused_question`。这是正确的展示默认值，但它发生在完整 Phase 23 artifact 已经生成之后。

当前没有独立的 Comment / Private / Paid 三档交付合同，也没有 `699` 付费层。`product_runtime` 仍直接暴露 Phase 20 sections。

关键冲突：

- Phase 23 每次都执行称骨、五年与 Yuan Renderer
- Phase 20 固定输出八段
- 因此现有 `focused_question` 只是后置裁剪，并没有改变默认计算和产品收据
- 续问裁剪已有测试，但没有付费续问的“只回答新增范围、不得复述完整报告”合同

## 6. 称骨触发路径

当前触发路径：

1. `mingli.phase19.calculate_chenggu(...)` 或 `mingli-phase19` CLI 可显式调用
2. `mingli.phase23.run_mingli_agent(...)` 无条件调用 Phase 19
3. Phase 20 无条件生成“称骨歌诀”第二段，即使歌诀正文不可用
4. `product_runtime` 无条件经 Phase 23 暴露八段 sections

已有安全边界：

- 核心包不含完整歌诀，`verse_available=false`
- 已确认四柱静态 Runtime 明确不计算称骨

未满足目标：称骨、骨重和称骨歌诀尚未做到默认彻底禁用。升级必须把它们改为严格显式点名才可调用，并保证默认输出、付费输出与续问收据中都不存在相关字段或文本。

## 7. 规则库与治理状态

当前存在多套不统一状态：

- `mingli.models.RULE_STATUSES`：`draft/reviewed/verified/deprecated`
- Phase 8 可执行状态：`reviewed/verified`
- 通用 `rule_loader` 默认生产状态：`reviewed/verified`
- `spec/rules` 实际统计：21 条 draft、6 条 reviewed、9 条 verified
- `knowledge/rules` 有 19 条 `production_allowed=false` 的 reviewed 来源规则
- Phase 9—17 的派生 profile 多使用布尔 `reviewed=true`，没有统一生命周期

现有优点：draft 在 Phase 8 会被 skipped；`production_allowed=false` 会被通用 loader 排除；现实证据可按 claim + scope 硬覆盖。

缺口：

- 没有固定的 `raw/draft/reviewed/production/rejected/pending_forward_test` 六状态合同
- 没有统一要求每条新增规则携带来源、适用范围、反例、审核人/审核时间
- `reviewed` 目前可以直接执行，不符合“只有 production 进入生产”的新目标
- 没有阻止作者自述命中、付款截图成为证据的专用字段级治理
- 受保护 `spec/` 中的旧状态不能直接改写；新生产路径需要独立的严格治理合同，并把旧资产当作兼容输入而非自动 production

## 8. 实盘评测与 forward test

当前 Real Case Learning V2 已具备：

- 预测先冻结、未来现实证据后采集
- 未来 evidence 的 observed_at 必须晚于冻结时间和事件窗口开始
- 时间切分使用 available_at、observed_at、event_window_end 与 cutoff
- 人工 adjudication、规则归因、版本比较与 temporal test partition
- 当前结果状态为 `hit/partial/miss/unverifiable`

缺口：

- 没有 `pending_forward_test` 规则状态
- 没有显式 maturity/due 状态或“到期前禁止结算”的单独门禁
- 现有 future outcome 可在事件窗口开始后记录；没有统一要求所有结算都等待窗口结束
- 没有目标分类：`exact_hit/partial_hit/miss/timing_error/category_error/unmet_condition/bad_input/no_feedback/invalid_prediction`
- 没有防止作者自称命中或付款截图进入证据链的专用来源禁用枚举

## 9. Hermes 与 PWA 适配入口

### Hermes 边界

本仓库没有 Hermes/Telegram adapter 源码，也没有可据此声称已集成或已部署的链路。可供外部适配器调用的本地入口是：

- `run_mingli_agent`
- `run_product_runtime`
- `classify_render_intent` / `render_phase23_intent`
- `intake_image_chart` / `confirm_image_chart_candidate`
- `run_confirmed_pillar_agent` / `render_confirmed_pillar_follow_up`
- HTTP/MCP 的 `/v1/mingli/analyze` 与 `analyze_mingli`

本升级可以保持这些公共入口兼容并新增本地合同，但不得据此宣称 Hermes、Telegram 或生产已验收。

### PWA 入口

- `web/pwa/src/runtime.ts` 在 Pyodide 内只加载 `DeterministicBaziEngine`
- PWA 做本地八字排盘、版本/哈希绑定、确定性、离线和移动 Chromium 验收
- PWA 当前不调用 Phase 23、付费 Renderer、AdviceRule 或六爻
- iOS/Android 实机安装与人工私密数据验收仍不在本审计运行范围

因此本次后端合同升级不应无关改写 PWA；如公共 wheel API 保持兼容，PWA 只需最终回归而无需产品功能扩张。

## 10. 阶段一基线验收

实际运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider \
  tests\test_runtime.py tests\test_bazi_engine.py tests\test_phase7_fact_graph.py \
  tests\test_phase17_special_scenarios.py tests\test_phase19_chenggu.py \
  tests\test_phase20_renderer.py tests\test_phase23_runtime.py \
  tests\test_render_intent.py tests\test_product_training_loop.py \
  tests\test_image_chart_intake.py tests\test_real_case_learning_v2.py
```

结果：`162 passed, 9 subtests passed in 149.07s`，退出码 0。

阶段闸门：`AUDIT_BASELINE=PASS`。下一阶段必须先以测试固化以下 RED：统一输入与降级、四维置信度、九类专题规则、AdviceRule、安全语言、称骨默认禁用、付费 focused 渲染、draft 隔离、forward-test maturity 和续问范围。
