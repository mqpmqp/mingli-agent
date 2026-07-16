# MingLi V2.0 Product Readiness

## 当前结论

目标状态是 `PRODUCT_CAPABILITY_READY` 与 `COMMERCIAL_VALIDATION_PENDING`。前者表示开发模式产品链可运行；后者表示仍禁止 production-commercial 模式和准确率/商业有效性声明。

## 能力闭环

| 能力 | 实际接线 | 证明锚点 |
|---|---|---|
| Intake / consent / privacy | 产品兼容层先检查分析同意、HMAC case_id 与 PII | `product_runtime.py` |
| ETL | 继续使用既有授权、时区、经度与平太阳时边界 | `validation_intake.py`, `validation_astro_etl.py` |
| Knowledge OS | 每次产品运行只读校验 knowledge tree，并记录内容 manifest hash | `knowledge.py`, runtime trace |
| Deterministic Engine | Phase 23 调用 `DeterministicBaziEngine` | `phase23.py` |
| Rules | Phase 7–16 实际计算，Phase 16 rule_set_hash 进入 envelope | Phase 7–16 artifacts |
| Evidence / reality | Phase 18 保持 claim/scope 级 reality hard override | evidence fusion trace |
| Confidence | 领域置信度最低值形成整体等级；low 明确 degraded | product envelope |
| Renderer | Phase 20 只渲染结构化结果，固定八段 | renderer sections/version |
| Feedback / training | 外置 JSON/JSONL、六对象合同、撤回与人工候选 | `training.py` |

统一输出包含 run/schema/engine/rule/renderer 版本，created_at，confidence/reason，limitations，使用的现实证据，八段 sections 与 trace。无法可靠计算时返回 structured `blocked`，不补写想象结果。

## Product Readiness Gate

产品门独立检查 runtime、Knowledge OS、rules、evidence、renderer、ETL、training、privacy、fast tests、build 与 static checks。`assess_v2_readiness` 只有在调用方明确提交这些门均通过时才返回 `PRODUCT_CAPABILITY_READY`。

Phase 24 兼容输出同时包含：

- 新字段：`product_capability_status`、`commercial_validation_status`、`development_runtime_allowed`、`production_commercial_allowed`；
- 旧字段：`product_release_status` 与 `product_release_ready`。

空真实案例集不再阻断开发模式 runtime，但旧 `PRODUCT_RELEASE_HOLD` 会继续保持，直到商业验证和正式授权全部满足。

## 已知限制

- 这是一套确定性文化研究/娱乐输出，不构成专业或决策建议。
- `PRODUCT_CAPABILITY_READY` 不证明命理预测准确率。
- Knowledge OS 的运行接线是只读治理/manifest 锚定；实际八字规则计算仍由版本化 Phase 7–16 资源完成。
- 本轮没有收集或导入真实案例，没有关闭 Commercial Validation Gate。
