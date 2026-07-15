# Real Case Data Model

真实数据位于 Git 外的受控 validation store。Git 只保存 schema、空模板、协议、聚合报告与不可逆 hash。

运行链固定为：intake → privacy processing → input validation → prediction generation → prediction freeze → reality evidence collection → blind review → adjudication → dataset freeze → benchmark → independent authorization。

核心对象：

- `RealCaseIntake`：不可逆 `person_case_id`、出生输入确认、consent 状态、采集 provenance 与预登记 scenario。
- `PredictionSnapshot`：引擎/规则/知识/input 版本、预登记 claims、`reality_evidence_visibility=false`、冻结时间与 canonical hash。
- `RealityEvidence`：独立来源、观察时间、采集时间、证据质量与 hash；不能回写 prediction。
- `ClaimComparison`：claim、时间窗、方向、现实证据引用、reviewer scores 与最终裁决。
- `ValidationDatasetManifest`：只含去标识索引、各对象 hash、聚合计数、门禁状态与 aggregate hash。
- `ProductReleaseAuthorization`：独立审批角色对特定 dataset/hash 的限时授权。

冻结对象不可原地修改。修正必须产生新 ID 或新 dataset version。`case_id`、`scenario_id`、记录数均不能替代 `person_case_id` 计人数。

Schema 位于 `src/mingli/contracts/schemas/`。模板位于 `validation/templates/`，模板不得填入真实资料后提交到 Git。
