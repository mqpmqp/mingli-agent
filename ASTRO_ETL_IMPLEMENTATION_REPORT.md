# Astro ETL Implementation Report

## 交付结果

- 新增 `mingli.validation_astro_etl`，将授权 Astro 来源记录转换为现有 `RealCaseIntake` 合同。
- 新增 `mingli validation astro-intake` 与 `scripts/astro_etl_pipeline.py`。
- 复用现有 HMAC-SHA256 假名化、PII scanner、intake validation、atomic batch import、duplicate detection 与 rollback 机制。
- 输入源文件、project salt 和 validation store 均强制位于当前 Git checkout 之外。

## 对原始脚本的修正

原始文件存在无法解析的字符串、缺失 import 和乱码。更重要的是，其数据模型假设不符合仓库合同：将公开资料等同 consent、把已知人生事件写成预测 claim、以无盐 MD5 处理身份、将 local mean solar time 称为 true solar time，并仅凭 Rodden rating 分配 Gold/Silver。实现已全部改为 fail-closed 边界。

## 未实现边界

- 不抓取 Astro-Databank，不调用网络 API。
- 不把 retrospective events 自动转成 `RealityEvidence`。
- 不计算包含时差方程的真太阳时。
- 不自动授予 Gold/Silver，不修改 validation closure 或产品发布授权。
- 不提交或打包真实姓名、真实出生资料、consent 文件或 project salt。
