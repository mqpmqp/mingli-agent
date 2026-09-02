# Internal Commercial Pilot V1 操作规程

## 目的和状态

本规程支持受控的内部试运行与真实案例的长期积累，不构成对外发布、准确率宣传或 Release Hold 解除。所有真实资料、同意记录、项目 salt、原始问题、运行结果和反馈都只能保存在受控的场外存储，不能进入 Git、测试 fixture、聊天记录或公开报告。

`mingli training` 只负责日常运营闭环。它的 feedback 和 outcome 永远不能单独构成商业验证证据：每条 outcome 固定标记为 `REAL_CASE_V2_ADJUDICATION_REQUIRED`。只有冻结的 Real Case Learning OS V2 案例、时间分割、双人独立审理和独立授权，才可以进入 Release Hold 再评估。

## 受控环境

1. 建立一个访问受限、已加密、位于 Git checkout 外的工作目录；由合规负责人管理访问和撤回请求。
2. 保存身份映射和 project salt 的系统必须与案例 JSON 存储隔离。案例侧仅可使用 `person:<HMAC-SHA256>` 伪匿名 ID。
3. 每个案例必须有可撤回的分析、研究、benchmark 和 training 范围授权；没有授权时仅可提供不持久化的分析，不能保存训练或案例记录。
4. 操作员、两位独立审阅者和裁决者必须是不同角色。审阅者在裁决前不得接触对方结论。

## 每日端到端链路

1. **用户提交资料与授权**：在场外采集资料，验证出生信息、问题范围、授权状态和撤回渠道。先完成不可逆去标识化，再创建案例引用。
2. **确定性运行**：将去标识化的运行输入放在场外，以受控 store 运行：

```powershell
mingli training run --input D:\controlled\case-input.json --store D:\controlled\training-store --repository-root D:\repo\mingli-agent --json
```

该运行依次覆盖确定性排盘、规则求值、预测时可见的 Reality Context、证据融合、置信度门禁与 Yuan 成品。运行输出必须保存其 `run_id`、canonical hash、规则版本、知识清单 hash 和 renderer 版本。

3. **冻结初始预测**：在用户确认前事、补充反馈或获得未来事件前，使用 Real Case Learning OS V2 的 `build_learning_case` 冻结排盘快照、原始问题、预测时现实上下文、结构化主张和初始预测。初始预测禁止携带预测后才可获得的 Reality Evidence。

4. **前事确认**：将只在预测生成前已发生且已知的事实登记为 prior-event validation；不得把它们当作未来 outcome，也不得修改冻结预测。

5. **未来反馈**：仅接受预测冻结之后开始的事件窗口。记录 event、observation 与 collection 时间，连同证据等级和来源。矛盾的已验证 Reality Evidence 必须进入人工协调，不能自动取一方。

6. **双盲审理与 Case OS**：两名独立审阅者分别给出 hit、partial、miss 或 unverifiable；不一致时交由独立裁决者。每个非 hit 结果登记 error taxonomy、规则归因、revision 建议和负样本归档；所有规则建议保持 `pending_operator_review`，绝不自动应用。

7. **时间分割和 Benchmark**：以事件与观察时间构建 train/test partition，检查人员、预测、派生指纹与近重复案例不能跨分区。只对冻结、授权、双人审理且可比较的 V2 记录计算规则覆盖、Reality Evidence 覆盖、不可验证率、Brier 和 ECE。

8. **独立复审**：用场外记录运行 `mingli-validation hold-reassessment`。即使达到协议阈值，输出仍为 `release_hold=ACTIVE`，只能请求独立产品授权人审查。

## 不可接受的捷径

- 用运行满意度、训练 feedback、调用方自填 claim ID、合成数据或公开传闻证明准确率。
- 在反馈后编辑初始预测、时间窗口、规则 ID 或 prediction hash。
- 将 outcome 标为商业验证合格而没有 V2 冻结主张、时间分割和双人裁决。
- 通过 `mingli training` 的 review 或候选规则直接修改规则包。
- 把 Release Hold 再评估、规则升级、发布、打 tag 或 PyPI 上传自动化。

## 最小审计包

每个真实案例仅在受控场外系统保留：同意范围及撤回状态、伪匿名 ID、冻结快照 hashes、运行版本、prior/future 时间戳、双人审理记录、分区 manifest hash、指标报告 hash 和裁决记录。任何撤回请求都必须生成不可反识别 tombstone，并失效所有派生记录。
