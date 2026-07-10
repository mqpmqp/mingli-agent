
# Rule Lifecycle

## 状态

`draft → reviewed → verified → deprecated`

### draft
来自单一资料、专家建议或模型抽取。不得直接支持高置信结论。

### reviewed
已核对来源、条件、排除项和白话解释。最多支持中置信判断。

### verified
至少满足一项：
- 多来源一致并经人工审核；
- 有足量案例支持；
- 通过明确的回测门槛。

### deprecated
被反例、回测或新版本替代。保留历史，不参与生产检索。

## 升级门禁

1. 唯一规则 ID
2. 来源可追踪
3. trigger / support / exclude 完整
4. 无绝对化结论
5. 至少一个正向测试与一个反向测试
6. Benchmark 不下降
