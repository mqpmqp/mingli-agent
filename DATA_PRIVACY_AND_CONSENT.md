# Data Privacy and Consent

## 最小权限原则

分析与训练是两个独立 consent scope：

- `analysis_allowed=true` 才能运行产品分析；
- `training_use_allowed=true` 才能写 TrainingCase/AnalysisRun；
- 未授权训练时返回正常分析结果和 `TRAINING_CONSENT_NOT_GRANTED`，store 保持不变。

case_id 必须由既有 `irreversible_person_case_id` 使用项目私有 salt 生成 HMAC-SHA256 `person:<64 hex>`。原始身份、salt、密钥、原始资料与真实 store 必须在 Git 外；CLI 不接受或打印 salt。

## 禁止数据

产品输入、训练记录和 audit 在落盘前扫描姓名类字段、手机号、邮箱和中国证件号模式。日志、候选和报告不得保存姓名、手机号、微信、邮箱、证件号或精确地址。出生合同仅用于授权分析，不进入产品 envelope 或训练 run 的公开摘要。

## 路径保护

解析后的真实 store 若等于 Git root 或位于其下，立即返回 `TRAINING_STORE_INSIDE_REPOSITORY`。只有测试显式 `--synthetic` 才可在仓库内使用合成 fixture；synthetic 记录不得进入商业验证。

既有 ETL 约束继续生效：

- consent 必须明确；
- Rodden rating 只描述来源，不自动授予案例等级；
- IANA timezone 必须有效；
- 经度修正只标为 local mean solar time，不冒充真太阳时；
- 真实 validation store 与 training store 都在 Git 外。

## 撤回

`training withdraw` 会删除关联 case/run/feedback/outcome/candidate，使相关 iteration 失效，并生成 tombstone。tombstone/audit 只保存 case_id 的再次 SHA-256 摘要、动作时间和失效计数，不保存 case_id 本身或任何原始身份。

撤回不等于抹除非个人化安全审计事实；审计只证明发生过撤回动作，不能用于重新识别人。
