# Ziwei Traditional Rule Content v1 Implementation Report

日期：2026-07-16

分支：`agent/ziwei-traditional-rule-content-v1`

基线：`82bca1599aefde27332eab055ce7f8a57d121ed1`

规则版本：`ziwei-traditional-rule-content@1.0.0`

## 实现结果

PR B 新增 184 条版本化、可执行、打包规则：168 条十四主星×十二宫、4 条四化、7 条基础亮度状态和 5 条同宫组合。每条规则具备 subject/star/palace/transformation/state、trigger、exclusions、priority、confidence、evidence_level、source_id、白话短句、lifecycle 与算法兼容性。

完整命盘会自动提取结构化规则事实；degraded、unsupported、算法版本不匹配及调用方覆盖派生事实均 fail closed。同一 domain、subject 与触发目标内最高 priority 生效，同目标同优先级相反方向保持 unresolved；不同目标的星曜落宫、四化、亮度与组合证据不会互相压掉。Reality Evidence 继续按同一 claim/scope 硬覆盖。

## Coverage 真实性

`build_rule_coverage` 不读取预填数字。它从规则索引取得 pair，为 168 条基础规则以及四化、亮度、组合规则分别构造最小事实并调用正式 evaluator；只有记录数量精确、身份唯一、实际匹配自身且未被排除时才计入。删除规则、篡改 trigger、复制 pair、新增第六条组合规则等 mutation 测试都会关闭门禁。

当前结果：168 records、168 behaviorally evaluated、0 duplicate pairs；状态为 `REVIEW_REQUIRED`，Rule Content Hold 仍 ACTIVE。

## 独立审查修复

独立 reviewer 与本地行为探针在首轮 GREEN 后发现三类 P2 缺陷：priority 原按整个 domain 压制，完整盘 27 个 match 中只有 3 个进入 Runtime evidence；重复宫名/宫序和不属于当前宫位的四化、亮度星仍可进入事实提取；非主星矩阵规则的错 trigger 或额外组合规则不会关闭 coverage。

- RED `d538241`：复现额外组合规则与重复宫名 false pass，目标结果 2 failed / 9 passed。
- RED `6e7c13e`：复现主星证据 0/14 有效、非法修饰星与重复宫序，目标结果 4 failed / 9 passed。
- GREEN `8691d7c`：冲突键收窄到同一 domain/subject/触发目标；命盘先过完整 Schema，再校验十二宫、二十八星、四化和修饰星归属；184 条规则逐类行为求值，受影响目标 14 passed。

修复后终审继续发现三项 P2：相同亮度状态但不同星仍共享冲突键；嵌套 `research_required` 记录仍被消费；非主星规则使用 `calculation_status==complete` 过宽 trigger 仍可通过 coverage。本地另补充“缺少 fail-closed exclusions” mutation。

- RED `fc8036c`：终审三项边界共 6 failed。
- RED `156bfa7`：exclusions mutation 1 failed。
- GREEN `840872d`：冲突键改为规范化 trigger；所有嵌套记录必须 `supported`；coverage 要求 canonical trigger 和必需 exclusions，并执行正样本、空目标、degraded、unsupported 四类行为求值；定向 7 passed，规则内容文件 45 passed。
- 测试闭环 `cab5d73`：将 primary/supporting/malefic/transformation/brightness × unsupported/research_required 的 10 个组合全部固化，10 passed。

## 内容和来源边界

规则只登记传统书籍 source metadata，并保存原创短句结构化转述。仓库没有复制长段原文、Metis 或其他外部平台解释，没有抓取第三方内容，也没有把传统规则标成 verified。内容不生成医疗、投资、法律或关系决定。

## 工程边界

- PR B 未修改 `ziwei_engine.py`、排盘公式、亮度表或 PR A benchmark。
- 三方四正、对宫、辅煞完整组合、完整格局和时间叠盘未实现。
- 规则覆盖率不表示预测准确率；真实案例与商业 Release Hold 继续 ACTIVE。
- PR B 在 PR A 合并前保持本地，不推送、不创建远端 PR。

## 验证摘要

- 聚焦规则/Runtime/CLI：63 passed。
- Ziwei 全集：96 passed。
- 目标模块覆盖率：88.24%（`ziwei_rules` 89%，`ziwei_runtime` 86%）。
- Ruff/Pyright/compileall：PASS。
- wheel package-data：PASS。
- 完整门禁、构建、安全与 artifact 扫描在 Local Merge Gate 报告中给出。
