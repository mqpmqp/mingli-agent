# MingLi Agent Core Runtime

## 紫微确定性排盘与传统规则内容 v1

`mingli ziwei chart` 已从空结构壳升级为版本化确定性排盘。已知出生时辰时，`ziwei-traditional-natal@1.0.0` 会输出命宫、身宫、十二宫干支、五行局、十四主星、十四辅煞、年干四化及版本化亮度状态；未知时辰仍返回 `degraded`，不会默认子时。公历/农历、闰月、IANA 时区、地方平太阳时、真太阳时和晚子时政策继续由既有输入归一化层处理。

```powershell
python -m mingli.cli ziwei chart --input birth.json
python -m mingli.cli ziwei benchmark
python -m mingli.cli ziwei coverage
python -m mingli.cli ziwei rules-validate
python -m mingli.cli ziwei rules-evaluate --input chart.json
```

固定盘 benchmark 覆盖水二、木三、金四、土五、火六局。规则内容 profile 为 `ziwei-traditional-rule-content@1.0.0`，打包 168 条主星×宫位短句规则、4 条四化、7 条亮度状态和 5 条同宫组合；每条规则均可由完整命盘事实实际匹配，coverage 由逐条行为求值计算。规则保持 `draft`，结果固定 `prediction_validity=not_evaluated`，不能替代现实证据、专业判断或真实案例验证。实现不调用 LLM、外部排盘 API，也不复制第三方平台解释。详细公式、来源和边界见 `docs/ziwei/README.md`、`docs/ziwei/RULE_SOURCES.md` 与对应实现报告。

## Astro 来源资料导入

已明确取得 research 与 benchmark consent 的 Astro 来源记录，可通过 fail-closed 转换器进入 Git 外受控 validation store。转换器使用 HMAC-SHA256 假名化身份，拒绝 `public_domain_historical` 代替 consent，也拒绝把 retrospective `events` 转成 prediction 前登记的 scenario。

```powershell
.\.venv-validation\Scripts\python.exe scripts\astro_etl_pipeline.py --file D:\private\authorized-astro-record.json --store D:\private\mingli-validation --source-ref authorized:astro-program --project-salt-file D:\private\mingli-project-salt.txt --dry-run
```

详细输入字段、安全边界与实际导入步骤见 `ASTRO_ETL_GUIDE.md`。

## 分离的测试门禁

安装开发依赖后，使用三条互斥命令运行验证：

```powershell
test-fast --timeout-seconds 300 --junitxml artifacts/test-fast.xml -- -q
test-benchmark --timeout-seconds 3600 --junitxml artifacts/test-benchmark.xml -- -q
test-real-case --timeout-seconds 600 --junitxml artifacts/test-real-case.xml -- -q
```

三条命令覆盖同一次 pytest collection 的全部测试，分别用于普通回归、长期 benchmark 与真实案例合同验证。CI 为每类测试设置独立 job、超时与 JUnit artifact。

## V2.0 技术发布范围

V2.0 技术候选版把确定性排盘、Fact Graph、P9–P16 结构规则、现实证据融合、特殊场景门禁、五年趋势和 Yuan 固定八段 Renderer 串成一个可审计的单进程流水线。调用入口是 `mingli.phase23.run_mingli_agent(...)` 或 `python -m mingli.phase23_cli run --input runtime.json`。

运行时不会接受调用方伪造的 `baseline_domains`；三个领域的基础状态必须来自 P16 合同。已核验现实证据可在同一 claim 与 scope 内覆盖结构结果，冲突和缺源会降低置信度。所有结果固定保留 `prediction_validity=not_evaluated`，最终答案只在末行出现一次“仅供文化研究与娱乐参考。”。

当前状态是 `technical_rc_only_product_hold`。V2.0 可以作为确定性技术发布交付，但产品状态仍为 `PRODUCT_RELEASE_HOLD`。P19 歌诀原文已按设计移出核心包，P19 算法继续输出骨重并固定 `verse_available=false`。合格真实验证案例仍为 0，因此没有产品准确率，也不允许宣称产品已验证。详见 `ARCHITECTURE.md`、`RUNBOOK.md`、`RELEASE_CHECKLIST.md` 和 `PRODUCT_VALIDATION_REPORT.md`。

MingLi Agent Core Runtime v2.0.0 是一个纯确定性的 Python 核心库。它把 `spec/` 中可验证的部分落成数据模型、规范校验、规则加载、证据融合、现实校正、置信度门禁、意图路由、中文渲染和静态策略检查。

Phase 9 adds an independent deterministic Bazi strength quantification layer:

```bash
python -m mingli.phase9_cli calculate --graph fact_graph.json
python -m mingli.phase9_cli validate
python -m mingli.phase9_cli benchmark
python -m mingli.phase9_cli profiles
python -m mingli.phase9_cli schemas
python -m mingli.phase9_cli provenance --expected-root .
```

The Phase 9 layer consumes Phase 7 Fact Graph data, emits profile-driven strength facts and evidence records, and keeps `prediction_validity=not_evaluated`. It does not emit GeJu, YongShen, XiJi, auspiciousness, event prediction, or natural-language readings.

本项目不是完整算命产品。Phase 5 只按公开约定计算四柱、历法转换、真太阳时校正以及大运顺逆和起运数值，不计算旺衰、大运序列、流年或事件预测，也不调用 LLM、OCR、数据库、Web 服务或外部排盘 API。调用方未选择确定性实现时，`UnavailableChartProvider` 仍会明确拒绝生成命盘，不会用示例盘冒充结果。

## 环境与安装

需要 Python 3.11 或更高版本。

```bash
python -m pip install -e ".[dev]"
```

运行时依赖仅有 `jsonschema`、其现代引用解析接口 `referencing` 与 `PyYAML`；Windows 额外安装 `tzdata`，为标准库 `zoneinfo` 提供 IANA 时区数据。`pytest` 是开发依赖。

## CLI

```bash
python -m mingli.cli validate-spec spec
python -m mingli.cli validate-rules spec/rules
python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl
python -m mingli.cli chart-validate --strict
python -m mingli.cli chart-benchmark --independent-only
python -m mingli.cli phase6 benchmark
python -m mingli.phase8_cli benchmark
```

- `validate-spec` 递归解析全部 JSON/JSONL，校验所有 JSON Schema 本身，并对同目录明确匹配的数据及规则数据执行 Schema 校验。错误包含文件、行号和 JSON 路径，任一错误返回非零状态。
- `validate-rules` 校验规则结构、状态和全局 ID 唯一性，不修改或升级规则状态。
- `benchmark-static` 检查 40 个黄金案例及 24 个实战盲测案例的确定性策略合同。结果不表示真实模型或命理预测准确率。

Phase 5 提供带版本标识的 `DeterministicBaziEngine`。每次成功结果都包含 `method_id`、完整约定与 `prediction_validity=not_evaluated`。详细口径见 `BAZI_CALCULATION_CONVENTIONS.md` 和 `BAZI_DETERMINISTIC_VERIFICATION_REPORT.md`；排盘成功不代表预测有效。

Phase 6 提供确定性静态派生结构映射层，只从 allowlisted Phase 5 结构化结果派生五项结构事实：地支藏干、可见天干十神、藏干十神、六十甲子纳音和旬空。它不计算大运/流年时间线、旺衰、格局、用神、喜忌、神煞、合冲刑害吉凶或事件预测；所有结果继续固定 `prediction_validity=not_evaluated`。

```bash
python -m mingli.cli phase6 map --input base_chart.json
python -m mingli.cli phase6 validate
python -m mingli.cli phase6 benchmark
python -m mingli.cli phase6 capabilities
python -m mingli.cli phase6 schemas
```

`phase6 map` 也可从 stdin 读取 JSON。stdout 只输出机器可读 JSON，错误写入 stderr；命令不读取网络、不调用外部模型、不修改输入文件。

Phase 7 在 Phase 5 和 Phase 6 之上构建确定性的八字事实图谱。它新增精确起运锚点、大运/流年时间线、显式年龄快照、十二长生结构事实、天干/地支结构关系以及 canonical graph SHA-256。它仍不计算旺衰、格局、用神、喜忌、吉凶、自然语言解读或事件预测。

```bash
python -m mingli.cli phase7 build --input base_chart.json
python -m mingli.cli phase7 timeline --input base_chart.json
python -m mingli.cli phase7 relations --input derived_chart.json
python -m mingli.cli phase7 validate
python -m mingli.cli phase7 benchmark
python -m mingli.cli phase7 profiles
python -m mingli.cli phase7 schemas
```

公共 API 位于 `mingli.phase7`：`build_bazi_fact_graph(...)`、`build_luck_timeline(...)`、`detect_structural_relations(...)`、`calculate_growth_stages(...)` 和 `benchmark_phase7(...)`。所有成功输出继续固定 `prediction_validity=not_evaluated`。

Phase 8 消费 Phase 7 Fact Graph，提供可运行但不生成命理解读的规则评估与证据合同。规则使用受限事实选择器和现实条件操作符；输出显式区分 `matched`、`not_matched`、`blocked`、`skipped`，并生成证据、冲突、现实硬覆盖、置信度输入、provenance 与 canonical hash。Phase 8 不内置旺衰、格局、用神、喜忌、吉凶或主题预测规则。

```bash
python -m mingli.phase8_cli evaluate --graph fact_graph.json --rules rules.json --reality reality.json --intent career
python -m mingli.phase8_cli validate --rules rules.json
python -m mingli.phase8_cli benchmark
python -m mingli.phase8_cli schemas
python -m mingli.phase8_cli provenance --expected-root .
```

公共 API 位于 `mingli.phase8`：`evaluate_rule_set(...)`、`parse_rule_set(...)`、`load_phase8_rules(...)`、`validate_phase8_rules(...)`、`benchmark_phase8(...)` 和 `validate_import_origin(...)`。所有成功输出继续固定 `prediction_validity=not_evaluated`。

Phase 16 消费 P15 的领域判断候选，只为事业、财运、感情建立确定性的基础判断合同。事业、财运、感情分别固定输出 10、9、8 个基础维度；规则只映射 P15 已激活的主题，未匹配维度保持 `unresolved`。合同显式携带置信度分数、支持与限制证据、缺失维度、现实覆盖和边界标志，并提供不包含具体事件的受控白话说明。P15 已确认的现实硬覆盖、冲突、置信度和证据 ID 原样保留，不跨目标或跨领域扩张。

```bash
python -m mingli.phase16_cli evaluate --phase15-result phase15_result.json
python -m mingli.phase16_cli query --result phase16_result.json --year 2028 --domain career
python -m mingli.phase16_cli validate
python -m mingli.phase16_cli benchmark
python -m mingli.phase16_cli rules
python -m mingli.phase16_cli schemas
python -m mingli.phase16_cli provenance --expected-root .
```

公共 API 位于 `mingli.phase16`：`evaluate_base_domain_contracts(...)`、`query_base_domain_contracts(...)`、`load_phase16_base_rules(...)`、`validate_phase16_rules(...)` 和 `benchmark_phase16(...)`。P16 不输出升职、录用、收入金额、盈亏、投资建议、结婚、复合、分手、外遇或对象数量等具体事件，也不提供自然语言命理结论；所有成功输出继续固定 `prediction_validity=not_evaluated` 与 `domain_contract_validity=base_rules_only`。

Phase 17 在 P16 上提供考公考编与复合特殊场景合同。考公严格拆分体制适配、上岸条件、考试倾向、岗位方向、备考策略五层；复合严格拆分缘分牵引、复联、复合、稳定四层。没有独立证据的考试倾向保持 `unresolved/low`，不会由其他层推断。现实硬条件只覆盖对应层，不会被盘面结构抵消。

```bash
python -m mingli.phase17_cli evaluate --phase16-result phase16.json --scenario career_exam --target-id TARGET --reality reality.json
python -m mingli.phase17_cli validate
python -m mingli.phase17_cli benchmark
```

Phase 18 统一现实字段别名、校验和 canonical hash，并按 claim + scope 编排 chart/timing/rule/case/reality 证据。已核验现实证据为 scoped hard override；相反证据仍保留，现实证据自身冲突时保持 unresolved。

```bash
python -m mingli.phase18_cli normalize --reality reality.json
python -m mingli.phase18_cli fuse --reality reality.json --evidence evidence.json
python -m mingli.phase18_cli benchmark
```

Phase 19 冻结 `chenggu-common-table-r1@0.1` 称骨权重表，使用整数“钱”完成年、农历月、农历日、民用时辰四项确定性求和。阳历输入会先转换为农历；闰月沿用同月权重并明确告警；性别不参与骨重计算。V2.0 核心包不包含完整歌诀原文、歌诀 package-data 或现代白话解释，结果固定 `verse_available=false`；未来如需歌诀，只能作为独立 optional verse pack 另行评审。该传统文化算法不具科学预测效力。

```bash
python -m mingli.phase19_cli calculate --input birth.json
python -m mingli.phase19_cli validate
python -m mingli.phase19_cli benchmark
```

Phase 20 提供 Yuan 固定八段 Renderer：资料确认、称骨歌诀、结论、事业、财运、感情、五年断事、建议。Renderer 只接受受控状态码与显式置信度，拒绝调用方注入 `overall_status` 或歌诀文本；未决状态只能使用低置信度。它严格保持段落顺序，并保证免责声明只在全文末尾出现一次；P19 固定 `verse_available=false`，因此歌诀段只展示骨重占位，不会自动补写。

```bash
python -m mingli.phase20_cli render --input renderer.json
python -m mingli.phase20_cli benchmark
```

Phase 21 生成以锚点年前后各两年组成的连续五年趋势合同。每年只输出事业、财运、感情的受控倾向、领域置信度、整体状态与整体置信度；无年度证据或冲突证据时保持低置信度。已核验现实证据仅在对应年份和领域硬覆盖。具体事件、金额、录用结果、复合结果和日期字段会被拒绝。

```bash
python -m mingli.phase21_cli generate --input outlook.json
python -m mingli.phase21_cli benchmark
```

Phase 22 提供真实案例导入与前事回测合同。Validation closure 要求至少 30 个合格唯一人员、至少 10 Gold、不超过 20 Silver、至少 100 个可比较 claims、三个场景以及完整审查与隐私覆盖；产品准确率许可独立要求至少 30 个合格 Gold 唯一人员，且审查与隐私覆盖通过。Silver 不能开启准确率声明。合成案例只用于程序合同测试。当前仓库合格真实案例为 0，因此不会输出伪造准确率，也不允许产品准确率宣称。

```bash
python -m mingli.phase22_cli run
python -m mingli.phase22_cli run --registry cases.json
python -m mingli.phase22_cli benchmark
```

Phase 23 提供单进程、无网络、无外部模型的端到端 Runtime，按固定顺序执行八字排盘、P19 称骨、P18 现实证据融合、P21 五年趋势与 P20 八段渲染。领域基础状态与总论均由已批准上游派生，调用方不能注入 `baseline_domains` 或 `overall_status`；状态与置信度共同通过 `confidence_gate` 进入 Renderer。Runtime 只允许已核验现实证据在 `runtime:baseline` 范围内覆盖对应领域。

```bash
python -m mingli.phase23_cli run --input runtime.json
python -m mingli.phase23_cli benchmark
```

Phase 24 汇总 P16—P23 基准并严格分离 validation closure、Gold-only 产品准确率声明门禁和产品发布授权。Validation closure 只会移除 `P22_VALIDATION_CLOSURE` blocker；即使准确率门禁通过，也不会自动移除 `PRODUCT_RELEASE_AUTHORIZATION`。P19 歌诀不是 V2.0 blocker，产品发布继续保持 hold。

```bash
python -m mingli.phase24_cli assess
python -m mingli.phase24_cli benchmark
```

真实案例验证 OS 使用 Git 外受控 store 完成 intake、隐私处理、预测冻结、现实证据、盲评、dataset freeze 和独立产品授权。公开仓库只包含协议、schema、空模板、聚合结果与不可逆 hash。当前没有授权真实案例，因而 `PRODUCT_RELEASE_HOLD` 与 `prediction_validity=not_evaluated` 保持不变。

```bash
python -m mingli.cli validation verify-protocol
python -m mingli.cli validation validate-intake --file case.json
python -m mingli.cli validation intake --file case.json --store /private/mingli-validation --source-ref authorized:program --dry-run
python -m mingli.cli validation freeze-prediction --file prediction.json --store /private/mingli-validation
python -m mingli.cli validation verify-freeze --file frozen_prediction.json
python -m mingli.cli validation privacy-scan validation validation_dataset_manifest.json product_release_authorization.json
python -m mingli.cli validation verify-dataset --file validation_dataset_manifest.json
python -m mingli.cli validation benchmark
```

完整数据合同、隐私政策和人工审查步骤分别见 `REAL_CASE_DATA_MODEL.md`、`PRIVACY_AND_CONSENT_POLICY.md` 与 `REVIEWER_RUNBOOK.md`。不得把填写后的模板、原始同意文件或真实案例提交到 Git。

## 核心约束

- 生产规则检索默认只返回 `reviewed` 与 `verified`，现实规则始终先于普通结构规则，再按优先级降序排列。
- 现实硬事实在证据融合中权重最高；分数只作汇总，不会自动生成命理结论。
- Phase 8 现实覆盖必须由规则显式声明 `reality_override_codes`，并且只覆盖已有 matched 证据的对应 claim。
- 同一 claim 的相反证据永久保留冲突记录；现实硬覆盖优先，其次按规则 priority，等优先级冲突保持 unresolved。
- 图片盘未确认时只请求确认并给出低置信限制说明。
- 考公输出分开处理体制适配、上岸条件、考试倾向、岗位与备考；复合输出分开处理缘分牵引、复联、复合与稳定。
- 医疗与投资场景优先现实专业处置；命理不能决定诊断、就医、杠杆或仓位。
- 固定免责声明只在答案末行出现一次，禁词在渲染完成前拦截。

## 测试

```bash
python -c "import mingli; print(mingli.__file__)"
python -m compileall src tests
python -m unittest discover -v
python -m pytest -q
python -m mingli.cli validate-spec spec
python -m mingli.cli validate-rules spec/rules
python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl
python -m mingli.cli chart-validate --strict
python -m mingli.cli chart-benchmark --independent-only
python -m mingli.cli phase6 validate
python -m mingli.cli phase6 benchmark
python -m mingli.cli phase7 validate
python -m mingli.cli phase7 benchmark
python -m mingli.phase8_cli provenance --expected-root .
python -m mingli.phase8_cli benchmark
git diff --check
```

`spec/` 是只读规范基线，开发和校验均不得改写其中的文件。
