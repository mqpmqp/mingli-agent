# MingLi Agent Phase 6：Bazi Derived Structure Scope Gate

## 1. Executive Verdict

建议把 Phase 6 定义为 **“Bazi Deterministic Derived Structure Engine v0.1”**，但仅限从已接受的 Phase 5 基础盘派生可复现、可版本化、可追溯的结构事实。它不是解读引擎，不得输出旺衰、格局、用神、喜忌、吉凶或事件预测。

推荐采用 **方案 C 的分层流水线**，并以方案 B 的独立 `DerivedChartResult` 作为派生层产物：

```text
BaseChart (Phase 5, frozen contract)
    -> DerivedStructure (Phase 6, independent contract)
    -> Interpretation (future, not Phase 6)
```

推荐首批只实现藏干、可见天干十神、藏干十神、纳音和旬空。十二长生、大运起止时间、年龄映射、合冲刑害关系需要先确定流派 profile 或边界；神煞及全部解释、预测能力排除在核心确定性层之外。

产品与架构决策已通过 `PHASE_6_R1_CONSERVATIVE_BOUNDARY_APPROVED` 锁定：v0.1 只包含五项静态核心；时间序列、十二长生、关系、神煞、解释和预测均排除；默认 strict 拒绝未决依赖，API 仅在显式 opt-in 时允许 partial。因此最终 Gate 为：

```text
PHASE_6_SCOPE_GATE_OPEN
```

本阶段没有开始实现业务代码。

## 2. Baseline Verification

- 仓库：`https://github.com/mqpmqp/mingli-agent`
- 新 worktree：`D:\Backup\Documents\命理师V2.0\mingli-agent-phase6-scope-gate`
- 分支：`agent/phase6-bazi-derived-structure-scope-gate`
- 基线：`1c8142b5540f6a008922caf55ac9f7f612c4737c`
- `HEAD`、`origin/main` 与用户指定基线三者一致。
- worktree 建立后为 clean；原 P0 worktree 未进入、未修改。
- Python：3.11.15；依赖安装在新 worktree 的 `.venv/`，该目录已被 `.gitignore` 排除。

基线实跑结果：

| 命令 | Exit | 结果 |
|---|---:|---|
| `python -m compileall -q src tests scripts` | 0 | 通过 |
| `python -m unittest discover -v` | 0 | 35 tests，OK，1 skipped |
| `python -m pytest -q` | 0 | 44 passed，1 skipped，2 subtests passed |
| `python -m mingli.cli validate-spec spec` | 0 | 通过 |
| `python -m mingli.cli validate-rules spec/rules` | 0 | 36 个规则 ID 唯一，状态未被修改 |
| `python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl` | 0 | 推理 40/40，实战结构 24/24 |
| `python -m mingli.cli knowledge-validate knowledge` | 0 | 通过 |
| `python -m mingli.cli knowledge-inventory knowledge` | 0 | batches 1、benchmarks 62、cases 6、concepts 38、evidence 27、rules 19、sources 4 |
| `python -m mingli.cli chart-validate --strict` | 0 | fixture 通过 strict 校验 |
| `python -m mingli.cli chart-benchmark --independent-only` | 0 | total/independent 52，passed 51，failed 0，unresolved 1，source_agreement 1.0 |
| `python -m mingli.cli pilot-verify knowledge/pilot_v0.1` | 1 | 当前 CLI 无此命令 |
| `python -m mingli.cli pilot-rollback knowledge/pilot_v0.1 --dry-run` | 1 | 当前 CLI 无此命令 |

最后两项是审查时发现的命令名称漂移，不是 Phase 6 回归失败；当前 CLI 提供的是 `knowledge-import` 与 `knowledge-rollback`。报告不声称不存在的命令通过。

## 3. Current Architecture Findings

### 3.1 Phase 5 引擎和结果合同

`DeterministicBaziEngine.calculate()` 接受 `ChartInput` 或 mapping，返回嵌套、可变、未类型化的 `dict`，没有正式的 `ChartResult` 类。当前结果包括：

- `method_id = bazi-deterministic-lichun-jie-noaa-v0.1`
- `calculation_version = 0.1.0`
- calendar、pillars、boundaries、luck、conventions、warnings
- `prediction_validity = not_evaluated`

全局 `CONVENTIONS` 是普通字典；尚无独立 convention profile ID、不可变类型或规范化摘要。把大量新字段直接塞入现有字典，会扩大无意破坏和序列化漂移的表面积。

`ChartInput` 是 strict/frozen dataclass，但与 mapping 输入不等价：mapping 路径支持农历闰月、经度和真太阳时等字段，而 dataclass 的公历日期校验不能表达所有农历输入。这是设计后续 typed adapter 时必须解决的兼容问题，不应在本 Scope Gate 中顺手重构。

### 3.2 Provider、schema 和兼容现状

- `ChartProvider` 只承诺返回 `Mapping[str, object]`；`UnavailableChartProvider` 明确拒绝伪造排盘。Phase 6 不应改变这两个合同。
- `spec/schemas/chart.schema.json` 是早期概念 schema，字段形状与当前 Phase 5 实际返回值不一致；`spec/` 是只读基线，Phase 6 不能借机修订。
- 当前包版本仍为 0.1.0，`mingli.__init__` 没有导出正式的 chart result 类型。
- 当前测试验证四柱、约定、闰月、真太阳时、范围和 benchmark 计数；没有独立验证 `luck.direction`、`luck.start_age_years` 或完整大运序列。
- `luck.start_age_years` 被舍入到 6 位小数。若将舍入年龄直接作为时间轴锚点，跨日、跨月、跨年的边界会产生不必要漂移；应先定义精确 `start_instant` 或精确 duration 合同。

### 3.3 CLI、CI 和文档

- `chart-validate` 验证 Phase 5 fixture；`chart-benchmark` 只比较四柱 expected 值。
- fixture 有 52 个 independent case：51 verified、1 unresolved。未决项是 2000-01-07 23:00 的日界/时柱来源冲突；runner 跳过 unresolved，不能把它描述为已验证。
- GitHub Actions 在 PR 到 main 和 main push 上运行完整测试、chart gates、patch whitespace，并保护 `spec/`、`knowledge/`。
- `BAZI_CALCULATION_CONVENTIONS.md` 已明确立春换年、十二节换月、00:00 换日、无早晚子时拆分、真太阳时、闰月、大运顺逆和起运算法。
- `BAZI_DETERMINISTIC_VERIFICATION_REPORT.md` 准确记录 52/51/0/1，但其中合并前 readiness 文字会随发布状态过时。
- 早期 `IMPLEMENTATION_REPORT.md`、`VERIFICATION_REPORT.md` 仍含“没有确定性排盘器”的历史陈述。此文档漂移与 Phase 6 代码无关，本阶段不改动。

## 4. Candidate Capability Classification

确定性等级：D1 为无 profile 歧义的机械映射；D2 为选定、版本化 profile 后可复现；D3 为解释或无法建立稳定唯一合同。

| 能力 | 等级 / 流派差异 | 输入依赖与输出合同 | 拒绝条件 / 验证 | 建议 |
|---|---|---|---|---|
| 地支藏干 | D2；藏干集合较稳定，但顺序、主中余气和权重有差异 | 每个支输出有序 `hidden_stems[]`，必须带 `mapping_profile_id`；首版不输出权重和气强 | 未知支、未知 profile 拒绝；12 支完整表，至少两独立来源 | Phase 6 首批 |
| 可见干、支对应十神 | 天干对天干为 D1；“地支十神”必须展开到藏干，不能给整个支一个含混标签 | 日主天干 + 目标天干；输出稳定 code、label、source/profile | 缺日主或非法干拒绝；完整 10×10 矩阵 | Phase 6 首批 |
| 藏干十神 | D2，继承藏干 profile | 每个藏干逐项输出 ten-god，不聚合成“地支十神” | 藏干未决则该项 unresolved；组合 fixtures | Phase 6 首批 |
| 六十甲子纳音 | D1 映射；解释是 D3 | 每柱输出 cycle index、nayin code/label，不输出意义 | 非法干支组合拒绝；60 项全覆盖 | Phase 6 首批 |
| 旬空 / 空亡 | D1 算术；用法解释有差异 | 每柱输出旬首、旬序、两个空支；明确基于哪个柱 | 非法甲子拒绝；60 项边界全覆盖 | Phase 6 首批 |
| 十二长生 | D2；阴干顺逆、土干寄生等存在实质流派差异 | 天干 + 地支 + growth profile，输出 stage 与 profile | 未选 profile 或来源冲突时拒绝/未决；每 profile 10×12 | 延后，除非产品批准 profile |
| 大运干支序列 | D2；依赖月柱及顺逆规则 | base ref + direction profile + count/range；输出每步干支和序号 | direction 未独立验证时拒绝；顺逆、阴阳年、性别组合 | 可进入时间序列子批次，不进首批静态核心 |
| 每步大运起止时间 | D2，高约定敏感 | 精确出生时刻、相邻节、方向、起运 profile；输出闭开区间与精确锚点 | 只有舍入年龄、边界未决、超范围时拒绝 | 延后至精确锚点合同完成 |
| 流年干支序列 | D2；“流年”边界需声明立春而非公历元旦 | 时间范围 + annual boundary profile；输出闭开区间、干支 | 未声明边界、超范围拒绝 | 可进入时间序列子批次 |
| 年龄/虚岁/周岁 | 周岁 D1；虚岁为 D2，存在春节/元旦及出生即一岁差异 | 出生 instant + 时间点 + age profile；分别输出，禁止单一 `age` | profile 缺失、区间非法拒绝 | 周岁可做；虚岁延后/参数化 |
| 大运/流年时间轴 | D2，继承全部上游约定 | 仅组合已验证序列；保持各层 provenance | 任一上游 unresolved 时部分结果或 strict 拒绝 | 最后子批次 |
| 合冲刑害破关系 | D2；关系集合、三合成局条件、自刑/暗合等边界不同 | 若做，只输出 type、参与者、profile、成立条件，不输出吉凶 | profile 未定或需强弱/成局判断时拒绝 | 建议从 v0.1 延后，或独立 `relations` 子能力 |
| 神煞 | D2/D3；名目、口诀、适用条件高度分散且常伴解释 | 很难形成精简核心合同 | 无可靠双源 profile 即拒绝 | 排除核心层；未来可选扩展 |
| 胎元、命宫、身宫、小运 | D2；算法版本多 | 需要独立 profile 和专门 fixture | profile 未定拒绝 | 延后 |
| 23:00 换日扩展 | 属 BaseChart convention，不是派生字段 | 必须重算基础日、时柱 | 当前已有来源冲突 | 不进 Phase 6；未来 BaseChart profile |
| 真太阳时以外地方时修正 | 属 BaseChart | 需要新的时间校正方法和来源 | 未定义算法即拒绝 | 延后 |
| 旺衰、格局、用神、喜忌 | D3 | 会产生命理判断 | 不应由结构层提供 | 永久排除 Phase 6 |
| 合冲刑害破吉凶、事件窗口和现实结果预测 | D3 | 解释/预测 | 一律拒绝 | 永久排除 Phase 6 |

结论：大运干支与流年序列在声明 profile 后属于可复现结构，原则上可进入 Phase 6，但不应与静态首批绑定发布；起止时间必须先补独立 oracle 和精确锚点。

## 5. Architecture Options and Trade-offs

### 方案 A：扩展 Phase 5 ChartResult

优点：单次调用、单个 payload；调用方取值最直接。

缺点：实际不存在 typed `ChartResult`，只是字典；新增 optional 字段会混合基础历法、派生映射和时间序列的 method/provenance；单项失败难以表达。

兼容风险：严格快照、消费者字段白名单、hash 和序列化顺序都可能变化。Phase 5 的 method ID 也会错误地为 Phase 6 逻辑背书。

schema 演进成本：高。旧概念 schema 与运行结果本已分叉，且 `spec/` 不可修改。

### 方案 B：新增 DerivedChartResult，引用基础 ChartResult

优点：基础合同保持冻结；派生层可独立 version、失败、benchmark 和回滚；来源、确定性等级与 profile 容易逐字段表达。

缺点：需要 orchestration、base reference 校验和第二份 schema；消费者需处理两个结果。

兼容风险：低到中。风险集中在如何稳定引用当前未类型化 base dict。

数据重复：只复制最小 pillar fingerprint 供审计，并用 canonical SHA-256 引用完整 base；不要复制完整 calendar/boundary payload。

### 方案 C：分层流水线

优点：结构事实与解释有强制边界；静态映射、时间序列和未来解释可分别 version；Phase 5 调用方零改动；未来旺衰、格局、用神若获准，也只能显式依赖结构层而不能污染它。

缺点：需要清晰的 stage protocol、capability negotiation、partial/error 语义和更多集成测试。

后续影响：能把未来解释阶段限制为独立 consumer，便于安全审计、禁用和替换。代价是实现前必须先确定引用和 version 合同。

### 已批准方案

采用 **C 的分层架构 + B 的结果对象**。A 与现状的无类型 dict、schema 漂移和 method/version 混用冲突最大。产品已批准该方案，并锁定 v0.1 为静态核心、排除 timeline/relations/twelve growth，采用 strict 默认与显式 partial API。

## 6. Recommended Phase 6 Boundary

首批静态核心建议包含：

1. 藏干（无权重）及 profile。
2. 可见天干相对日主的十神。
3. 每个藏干相对日主的十神。
4. 四柱各自纳音。
5. 四柱各自旬与旬空。

第二批候选为大运干支和流年序列，但只有在 Phase 5 现存 luck direction/start 字段完成独立验证后才进入。大运起止时间、虚岁、组合时间轴另设后续批次。十二长生、relations 只有经 profile 决策后才可作为可选 capability。

不进入 Phase 6：神煞、胎元/命宫/身宫、小运、基础日界流派扩展、其他地方时修正，以及所有旺衰、格局、用神、喜忌、吉凶解释和事件预测。

Phase 6 成功只表示结构计算按已声明方法完成，不能表述为预测有效；所有成功和部分成功结果都保留 `prediction_validity: not_evaluated`。

## 7. Proposed Data Contracts

### 7.1 模型草案

```text
BaseChartRef
  base_method_id: str
  base_calculation_version: str
  base_result_sha256: str
  pillar_fingerprint: str
  base_convention_digest: str

DerivedConventionProfile
  profile_id: str
  profile_version: str
  components: {capability: mapping/profile version}
  canonical_sha256: str

DerivedChartResult
  schema_version: str
  method_id: str
  calculation_version: str
  convention_profile: DerivedConventionProfile
  base_ref: BaseChartRef
  status: complete | partial | refused
  day_master: StemRef
  pillars: list[DerivedPillar]
  timelines: optional TimelineResultRef
  ambiguities: list[DependencyAmbiguity]
  warnings: list[str]
  prediction_validity: literal[not_evaluated]
```

每个新增字段还要有机器可读的：`source_ids[]`、`determinism_level`、`verification_status` 和 `capability_version`。字段缺失和字段 unresolved 必须可区分。

十神使用稳定 code，例如 `peer_same_polarity`、`peer_opposite_polarity`、`output_same_polarity` 等十个枚举；中文“比肩/劫财……”作为 label，不作为唯一语义键。地支不直接给单一十神，必须通过藏干逐项表达。

### 7.2 建议 JSON 示例

```json
{
  "schema_version": "bazi-derived-structure-result@0.1",
  "method_id": "bazi-derived-structure@0.1.0",
  "calculation_version": "0.1.0",
  "convention_profile": {
    "profile_id": "derived-static-canonical-v0.1",
    "profile_version": "0.1.0",
    "components": {
      "hidden_stems": "hidden-stems-profile-a@1",
      "ten_gods": "ten-gods-stem-polarity@1",
      "nayin": "sexagenary-nayin@1",
      "xunkong": "sexagenary-xunkong@1"
    },
    "canonical_sha256": "sha256:..."
  },
  "base_ref": {
    "base_method_id": "bazi-deterministic-lichun-jie-noaa-v0.1",
    "base_calculation_version": "0.1.0",
    "base_result_sha256": "sha256:...",
    "pillar_fingerprint": "甲子|丙寅|戊辰|庚申",
    "base_convention_digest": "sha256:..."
  },
  "status": "complete",
  "day_master": {"code": "wu", "label": "戊"},
  "pillars": [
    {
      "position": "year",
      "stem": {"code": "jia", "label": "甲"},
      "branch": {"code": "zi", "label": "子"},
      "stem_ten_god": {
        "code": "authority_same_polarity",
        "label": "七杀",
        "determinism_level": "D1",
        "verification_status": "verified",
        "source_ids": ["source-a", "source-b"]
      },
      "hidden_stems": [
        {
          "ordinal": 1,
          "stem": {"code": "gui", "label": "癸"},
          "ten_god": {"code": "wealth_opposite_polarity", "label": "正财"}
        }
      ],
      "nayin": {"code": "sea_gold", "label": "海中金"},
      "xunkong": {"xun_start": "甲子", "void_branches": ["戌", "亥"]}
    }
  ],
  "timelines": null,
  "ambiguities": [],
  "warnings": [],
  "prediction_validity": "not_evaluated"
}
```

示例只说明形状，不是 benchmark oracle；code 命名须在实现前冻结并以 schema 测试。

### 7.3 建议错误代码

- `DERIVED_BASE_RESULT_INVALID`
- `DERIVED_BASE_METHOD_UNSUPPORTED`
- `DERIVED_BASE_FINGERPRINT_MISMATCH`
- `DERIVED_CONVENTION_PROFILE_REQUIRED`
- `DERIVED_CONVENTION_UNSUPPORTED`
- `DERIVED_DEPENDENCY_UNRESOLVED`
- `DERIVED_FIELD_NOT_AVAILABLE`
- `DERIVED_CAPABILITY_NOT_ENABLED`
- `DERIVED_OUTPUT_SCHEMA_INVALID`
- `TIMELINE_DIRECTION_UNVERIFIED`
- `TIMELINE_START_ANCHOR_UNVERIFIED`
- `TIMELINE_RANGE_INVALID`
- `TIMELINE_OUT_OF_SUPPORTED_RANGE`
- `AGE_CONVENTION_REQUIRED`

错误对象至少含 `code`、`message`、`field_path`、`dependency`、`method_id`、`profile_id`；不得用 warning 替代应拒绝的输入错误。

## 8. Proposed CLI and Python API

### 8.1 CLI

新增命令，不扩展 Phase 5 现有命令语义：

```text
mingli chart-derived-validate FIXTURE [--strict]
mingli chart-derived-benchmark FIXTURE --independent-only
mingli chart-derive --base BASE.json --profile PROFILE_ID \
  --capability hidden-stems --capability ten-gods --output RESULT.json
mingli chart-timeline --base BASE.json --profile PROFILE_ID \
  --from YYYY-MM-DD --to YYYY-MM-DD --output TIMELINE.json
```

`chart-derive` 默认无网络、JSON 写 stdout；显式 `--output` 时不覆盖已有文件，除非未来另设明确 `--force`。`--strict` 遇到任何 unresolved dependency 返回非零；非 strict 可输出 `status=partial`，但仍不得把 unresolved 计入 PASS。`chart-timeline` 只有在时间序列子批次获准后才实现。

### 8.2 Python API

```python
class DerivedStructureProvider(Protocol):
    def derive(
        self,
        base_chart: Mapping[str, object],
        *,
        capabilities: frozenset[str],
        convention_profile: DerivedConventionProfile,
        strict: bool = True,
    ) -> DerivedChartResult: ...

class TimelineProvider(Protocol):
    def build(
        self,
        base_chart: Mapping[str, object],
        derived_chart: DerivedChartResult,
        *,
        start: date,
        end: date,
        convention_profile: TimelineConventionProfile,
    ) -> TimelineResult: ...
```

Phase 5 的 `ChartProvider`、`UnavailableChartProvider` 和 `DeterministicBaziEngine.calculate()` 保持原签名、原输出方向。新层通过 adapter 校验 base dict 后工作，不要求旧调用方迁移。

## 9. Convention and Versioning Plan

1. 冻结 Phase 5 `method_id` 和结果字段，不用 Phase 6 的变更升级它。
2. Phase 6 分开记录 `schema_version`、`method_id`、`calculation_version` 和 `convention_profile`。
3. profile 按 capability 组合版本：hidden stems、ten gods、NaYin、XunKong、growth、luck direction、luck start、annual boundary、age 各自独立。
4. 对 profile 采用排序键、UTF-8、无空白的 canonical JSON 后计算 SHA-256；同样生成 base result/ref 摘要。
5. 纯 bug 且输出合同不变升级 calculation patch；映射或约定改变必须新 profile；字段兼容新增升级 schema minor；破坏性形状改变升级 schema major。
6. 维护允许的 `base_method_id + base_calculation_version` 兼容矩阵。未知 base method 明确拒绝，不做“尽力猜测”。
7. migration 是重新从冻结 base result 派生新结果，保留旧结果和旧 profile；禁止原地重写历史产物。

## 10. Benchmark and External Validation Plan

### 10.1 实现入口最低数量

首批静态核心建议至少 **272 个独立 assertion/case**：

- 100：10 个日主天干 × 10 个目标天干的完整十神矩阵。
- 12：十二地支藏干全集，逐项校验顺序和数量。
- 60：六十甲子纳音全集。
- 60：六十甲子旬首/旬空全集。
- 40：藏干十神组合、来源/provenance、非法输入、partial、序列化稳定性、Phase 5 旧结果兼容。

若纳入十二长生，每个获准 profile 再加 120（10×12），即至少 392。若纳入时间序列，再加至少 88：方向组合 20、顺逆序列 20、起运跨日/月/年 24、流年/立春 8、年龄 8、错误与兼容 8。完整首版因此不应低于 480。

数量是下限，不替代来源独立性和边界覆盖。

### 10.2 必须外部独立核验的分类

- 10×10 十神映射、12 支藏干、60 纳音、60 旬空、每个十二长生 profile：至少两个相互独立、版本固定的来源。
- 大运顺逆、起运锚点、流年立春边界、虚岁 profile：至少两个独立来源，并保留可复算中间量。
- 23:00、跨节、跨年、闰月等依赖基础柱的样例：不得只引用项目 Phase 5 输出；要保留外部 expected 与来源版本。
- 序列化和 compatibility 属项目合同测试，不要求外部命理 oracle，但必须固定 canonical fixture。

独立性规则：同一作者的多语言 port 不算两源；使用同一底表的两个库不算完整独立；不能用同一 Python 库同时做实现和唯一 oracle；项目自身输出永远不是 independent expected。

已审查的候选资料包括：[香港天文台干支说明](https://www.hko.gov.hk/en/gts/time/stemsandbranches.htm)、[二十四节气](https://www.hko.gov.hk/en/gts/time/24solarterms.htm)与[公农历对照表](https://www.hko.gov.hk/en/gts/time/conversion.htm)，可作为历法和六十周期权威锚点；[lunar-python](https://github.com/6tail/lunar-python)、[sxtwl](https://github.com/skydancep/sxtwl)和[cnlunar](https://github.com/OPN48/cnlunar)可用于实现差异比对，但必须核对其共同数据来源和具体版本。传统表还应交叉核验公开原典，例如[《三命通会》卷一](https://ctext.org/wiki.pl?chapter=926860&if=en)、[《渊海子平》](https://zh.wikisource.org/zh-hans/%E6%B7%B5%E6%B5%B7%E5%AD%90%E5%B9%B3)；[《滴天髓阐微》](https://zh.wikisource.org/wiki/%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE)对阴阳干长生顺逆存在不同论述，证明十二长生不能静默固定单一流派。

所有 fixture 记录 `verification_source`、`source_version`/commit、页码或锚点、访问日期、license、timezone、longitude、calendar/day-boundary/solar-term profile、`independent=true`。来源冲突标记 `status=unresolved`，不自动选择、不计 PASS，并进入报告的冲突表。

### 10.3 测试矩阵

| 层级 | 必测内容 |
|---|---|
| 单元 | 十神全矩阵、藏干表、NaYin、旬空、profile dispatch、稳定 code |
| 属性 | 合法六十甲子闭包、旬空始终两个支、序列顺逆可逆、无解释字段 |
| 合同 | strict schema、未知字段策略、canonical JSON/hash、错误对象、`prediction_validity` |
| 依赖 | 不支持 base method、base hash 不符、23:00 unresolved、unsupported year、缺输入 |
| 时间序列 | 阴阳年/性别、顺逆、起运跨日/月/年、流年立春、公历年边界、年龄 profile |
| 兼容 | Phase 5 fixtures 原样通过；旧 provider/CLI 输出字节语义不变 |
| 安全 | 无解释/预测措辞、无网络、无 PII fixture、超大 range 有界拒绝 |
| CI | protected path、完整旧门禁、新 derived validate/benchmark、diff check |

## 11. Compatibility and Migration Plan

- 不向 Phase 5 payload 添加字段；旧调用方继续只调用 `calculate()`。
- 新调用方显式调用 Derived provider；通过 `BaseChartRef` 和兼容矩阵绑定基础结果。
- 第一版只接受当前 Phase 5 method/version；以后新增 adapter，而不是在核心逻辑中猜字段。
- 新合同放在 implementation-owned 路径（具体位置由实现 PR 决定），不能修改只读 `spec/`。
- 新字段只做 additive minor；删除、重命名、枚举语义变化都要新 major/profile。
- 历史派生结果不可原地升级。migration 读取原 base、选择新 profile、生成并列的新 result，记录 old/new hash 和工具版本；失败不删除旧产物。
- 不把 Phase 6 字段注入 Core Runtime renderer、Knowledge OS rule 或 Evidence Engine，直到另有明确消费合同和安全审查。

## 12. Security / Safety / Claim Boundaries

- 结构计算成功不等于预测有效；固定输出 `prediction_validity: not_evaluated`。
- 禁止 personality、财富、婚姻、职业、健康、吉凶、事件窗口或现实结果判断。
- 无 LLM、外部排盘 API、数据库或网络运行时依赖；外部资料只用于离线 fixture 审核。
- 输入 range、时间序列跨度、capability 数量必须有上限，避免资源滥用；错误不得泄露本地路径或原始个人资料。
- benchmark 优先使用合成/历史公开数据，不提交真实个人出生资料。
- 缺经度时仍不得声称真太阳时校正；派生层继承并展示 base provenance，不能修饰或掩盖 base warning。
- 关系若未来实现，只输出结构匹配及 profile，不输出“好/坏”“应验”。
- 新模块默认无副作用；不修改 `spec/`、`knowledge/`，不接入现有解释 renderer。

## 13. Implementation Batches

以下仅为计划，未实施：

1. **Batch 0 — 决策与 fixtures**：批准架构、首版 capability、partial policy、profile；建立双源 manifest 和 independent expected。没有足量 fixture 不写 engine。
2. **Batch 1 — 合同与 base adapter**：typed immutable models、canonical serialization/hash、base compatibility matrix、错误代码；保持 Phase 5 API 原样。
3. **Batch 2 — 静态核心**：藏干、十神、NaYin、旬空；先写完整表格/矩阵测试，再实现纯函数。
4. **Batch 3 — CLI 与 gates**：独立 `chart-derived-*` 命令、strict/partial 语义、CI 和 protected-path 检查。
5. **Batch 4 — 可选 profile**：只有决策批准且双源通过后加入十二长生或 relations；默认关闭。
6. **Batch 5 — 时间序列**：先独立验证现有 luck direction/start，再实现大运干支、精确起止、流年、年龄和组合 timeline；可拆 PR。

每批都需小 diff、旧测试全绿、独立 benchmark 无 fail；unresolved 单列且不能提升 readiness。

## 14. Entry Criteria

进入实现阶段前必须满足：

1. C+B 架构、静态核心范围和独立结果对象已由 `PHASE_6_R1_CONSERVATIVE_BOUNDARY_APPROVED` 确认。
2. timeline、十二长生和 relations 已明确排除 v0.1，不能在实现阶段重新扩大范围。
3. 23:00 policy 已锁定：strict 默认整单拒绝；仅显式 API opt-in 允许 partial，并传播字段级 ambiguity。
4. 首批至少 272 个独立断言，传统映射表具备双源、版本和 license 记录；若扩大范围按第 10 节增加。
5. 现存 `luck.direction` 与 `start_age_years` 在进入 timeline 前获得独立验证；定义不依赖舍入年龄的精确起运锚点。
6. 冻结 stable code、schema、canonical JSON/hash 和 base compatibility matrix。
7. `spec/` 概念 schema 与运行合同的差异被明确接受，不要求 Phase 6 修改只读规范。
8. CI 设计含旧门禁、derived 门禁、protected paths 和不含预测字段的合同测试。

## 15. Blockers and Open Questions

产品/架构问题已关闭：

1. 批准“分层流水线 + 独立 DerivedChartResult”。
2. Phase 6 v0.1 仅包含静态核心；timeline 进入未来独立阶段或子版本。
3. relations 与十二长生完全排除 v0.1。
4. 23:00 默认 strict 整单拒绝；API 仅显式 opt-in partial。
5. 未来 canonical 起运值必须使用 exact instant 或 exact duration；舍入年龄仅供展示。
6. implementation-owned schema 固定在 `src/mingli/contracts/schemas/`，必须作为 package data 随 wheel 发布。

技术阻塞：

- Phase 5 benchmark 不验证已输出的 luck direction/start；timeline 不能据此宣称已验证。
- 当前 base 是无类型 dict，必须先有只读 adapter 和 canonical fingerprint。
- 23:00 有一个真实外部来源冲突，不能让 runner 的 skip 语义污染时柱派生 PASS。
- 十二长生存在可追溯的流派冲突；未选 profile 前没有唯一 expected。
- 旧概念 schema、当前运行结果和部分历史文档存在漂移；不能通过修改 `spec/` 偷偷消除。

## 16. Product / Architecture Decision Record

Decision ID：`PHASE_6_R1_CONSERVATIVE_BOUNDARY_APPROVED`。

### 16.1 架构

- 批准 `BaseChart -> DerivedStructure -> Interpretation` 分层流水线。
- 使用独立 `DerivedChartResult`；Phase 5 BaseChart 合同、`calculate()` payload、method ID 和 calculation version 保持冻结。
- Phase 6 只通过只读 adapter 消费明确兼容的 Phase 5 base result，不猜测、不修正、不重算基础盘。
- Interpretation 不属于 Phase 6。

### 16.2 v0.1 静态核心

- 地支藏干：有序输出，携带 mapping profile；无权重、主中余气强弱解释。
- 可见天干十神：日主为参照，四柱天干分别输出；稳定英文 code，中文仅为 label。
- 藏干十神：逐个藏干输出，不把整个地支压缩为单一十神。
- 六十甲子纳音：四柱分别输出结构映射，无性格、吉凶或事件解释。
- 旬空/空亡：四柱分别输出旬首、旬序和两个空支，无吉凶解释。

### 16.3 明确排除

v0.1 排除大运/流年及组合 timeline、起止时间、周岁/虚岁、十二长生、所有合冲刑害破/三合三会半合暗合自刑、神煞、胎元、命宫、身宫、小运、23:00 新流派、真太阳时以外地方时修正、旺衰、格局、用神、喜忌、吉凶、事件窗口，以及人格、财富、婚姻、事业、健康和任何现实结果预测。

不得接入 LLM、外部排盘 API、数据库、网络运行时服务、Core Runtime renderer、Knowledge OS production rules 或 Evidence Engine 推断路径。

### 16.4 未决依赖策略

- 默认 `strict=true`。基础日柱或时柱依赖 unresolved 时整次请求以 `DERIVED_DEPENDENCY_UNRESOLVED` 拒绝；unresolved 永不计 PASS。
- API 可在显式 `strict=false` 时返回 partial：只保留不依赖未决字段的稳定结果；所有依赖日柱/时柱的字段标为 unresolved；`status=partial`；`ambiguities` 记录来源与字段路径；warnings 明示基础盘未决。
- CLI v0.1 不允许隐式 partial，只能通过显式参数启用。

### 16.5 时间序列、schema 与版本

- timeline 不在 v0.1。未来 canonical 起运值必须是 exact instant 或 exact duration；`start_age_years` 六位小数只能展示，不能作为唯一锚点。实现 timeline 前必须独立验证 Phase 5 luck direction 与起运算法。
- implementation-owned schema 固定在 `src/mingli/contracts/schemas/`，随 wheel/package-data 发布，并有安装后读取测试；不得依赖 source checkout，不修改 `spec/schemas`。
- Phase 6 固定：`schema_version=bazi-derived-structure-result@0.1`、`method_id=bazi-derived-structure@0.1.0`、`calculation_version=0.1.0`。
- hidden_stems、ten_gods、nayin、xunkong profile 分别版本化；映射或约定变化创建新 profile，不原地改写历史 profile。

### 16.6 安全与状态合同

所有 complete/partial 结果必须包含 `prediction_validity: not_evaluated`。不得出现 good/bad、auspicious/inauspicious、personality、wealth、marriage、career、health、event prediction，或依据盘面结构生成的 recommendation。

```yaml
architecture:
  layered_pipeline: approved
  independent_derived_result: approved

phase_6_v0_1:
  static_core_only: true
  timelines: excluded
  twelve_growth: excluded
  relations: excluded
  shensha: excluded
  interpretation: forbidden
  prediction: forbidden

dependency_policy:
  strict_default: true
  explicit_partial_api: allowed
  unresolved_counts_as_pass: false

implementation_started: false
spec_modified: false
knowledge_modified: false
prediction_added: false
```

## 17. Final Gate Decision

Phase 6 的架构、v0.1 保守范围、未决依赖、timeline、schema/version 与安全边界均已由产品批准。Batch 0/1 可在 PR #8 合并且 main push CI 通过后，从最新 `origin/main` 的全新 clean worktree 开始。

```text
PHASE_6_SCOPE_GATE_OPEN
```

```yaml
implementation_started: false
spec_modified: false
knowledge_modified: false
prediction_added: false
```

