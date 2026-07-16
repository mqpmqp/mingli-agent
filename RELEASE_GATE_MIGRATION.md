# Release Gate Migration

## 变更原因

旧 Phase 24 只有 `PRODUCT_RELEASE_HOLD/ALLOWED`，并把技术 RC、真实案例 closure 和正式产品授权组合在同一结论里。该字段继续用于最终商业发布，但不能准确表达“产品开发能力已经闭环，商业验证尚未完成”。

## 新旧字段映射

| 新字段 | 含义 | 旧字段兼容 |
|---|---|---|
| `product_capability_status` | `PRODUCT_CAPABILITY_READY/BLOCKED` | 技术链就绪，不代表发布授权 |
| `commercial_validation_status` | `COMMERCIAL_VALIDATION_PENDING/READY` | 商业验证未完成时旧字段继续 HOLD |
| `development_runtime_allowed` | 产品能力门通过后可运行开发模式 | 不改变 `prediction_validity` |
| `production_commercial_allowed` | 产品与商业门均通过 | 与最终 `product_release_ready` 对齐 |
| `product_release_status` | 旧 `PRODUCT_RELEASE_HOLD/ALLOWED` | 保留，不删除、不重命名 |

Phase 24 schema 升级为 `release-candidate-assessment@0.6`。原有 Python 字段、旧状态值和默认 fail-closed 语义保留；只新增字段。现有调用方可以继续读取旧字段，新调用方应优先读取双门状态。

## 模式规则

- Product ready + Commercial pending：允许 development，禁止 production-commercial，旧状态 HOLD。
- Product blocked：两种模式都禁止。
- Product ready + Commercial ready + 正式授权：才允许 production-commercial，旧状态才可能 ALLOWED。

Phase 22 空数据检查仍作为“验证系统能诚实报告未评估”的技术契约测试存在，但缺少大规模真实案例不再把 development runtime 判为不可运行。未经授权案例和 Training Feedback 永远不能清除 Commercial Validation Gate。
