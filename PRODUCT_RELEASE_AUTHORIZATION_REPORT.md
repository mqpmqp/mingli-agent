# Product Release Authorization Report

```yaml
authorization_status: pending
dataset_id: null
validation_closure_passed: false
product_accuracy_claim_allowed: false
product_release_status: PRODUCT_RELEASE_HOLD
authorized_by_role: null
```

当前不存在可供独立审批者审查的真实 frozen dataset，因而不能签发产品发布授权。Validation closure、accuracy claim 和 product release authorization 是三个独立门禁；前两者均不能自动推导第三者。

授权必须引用当前 dataset ID、aggregate canonical hash 与 validation report hash，注明使用范围、禁止声明、限制、冲突、审批角色和复审/过期时间。任何 pending、rejected、revoked、expired、hash 不匹配或外部门禁失败均保持 HOLD。
