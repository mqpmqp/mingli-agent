# 紫微测试缺口矩阵

## 基线

- 紫微选择测试：`python -m pytest -q -k "ziwei or purple_star"` → 0 selected（仓库无紫微测试）。
- 快测门禁：`python -m mingli.test_gates --timeout-seconds 600 fast -- -q` → `177 passed, 1 skipped, 90 deselected, 16 subtests passed`。

| 类别 | 任务前状态 | P0 自动化目标 |
|---|---|---|
| Schema 合法/非法/枚举/required | 完全缺失 | JSON Schema 与 Python 合同测试 |
| 公农历等价 | 完全缺失（紫微） | 归一化结果与 fingerprint 相同 |
| 经度与均时差分项 | 完全缺失（紫微） | 修正分量和模式断言 |
| 真太阳时跨时辰/跨日 | 完全缺失 | 精确分钟边界夹具 |
| 23:00/00:00 与晚子时 | 完全缺失 | 两种政策的日期身份测试 |
| 节气边界 | 已实现且有测试（八字） | 复用行为不回归；紫微不另造算法 |
| 闰月/时区 | 已实现且有测试（通用） | 紫微输入、上下文、fingerprint 保留 |
| 未知时辰 | 完全缺失 | degraded/unsupported，无伪造时辰 |
| 重复计算/JSON/版本指纹 | 完全缺失 | 稳定性和版本敏感性 |
| 姓名/显示年龄非身份 | 完全缺失 | 属性变化不改变 fingerprint |
| A/B 命盘、用户、案例隔离 | 完全缺失 | scope/cache namespace 负向测试 |
| 合盘 A-B/A-C | 完全缺失 | pair hash 与顺序隔离 |
| 旧请求覆盖 | 完全缺失 | revision/context stale rejection |
| 月/日/时上下文完整性 | 完全缺失 | 缺父上下文必须失败 |
| 规则 priority/exclusions/required | 完全缺失 | 最小无内容规则引擎测试 |
| reality hard override | 已实现且有测试（Phase18） | 紫微适配后的端到端回归 |
| 低置信强结论拦截 | 完全缺失（紫微） | controlled status + forbidden language |
| Yuan 八段/免责声明 | 已实现且有测试（Phase20） | 紫微适配器回归 |
| 匿名案例同意/撤回 | 完全缺失 | Schema 负向测试 |

所有新增测试必须真实运行；不会通过 skip、放宽断言或伪造 fixture 提升覆盖率。

