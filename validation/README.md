# Validation workspace boundary

此目录只保存空模板、协议辅助文件、机器可读聚合结果和说明。不要把填写后的真实 intake、prediction、reality evidence、review、adjudication、consent 或身份映射提交到仓库。

真实数据必须导入 Git checkout 外的受控 store，例如：

```powershell
python -m mingli.cli validation intake --file case.json --store D:\Private\mingli-validation-store --source-ref authorized:case-program --dry-run
python -m mingli.cli validation intake --file case.json --store D:\Private\mingli-validation-store --source-ref authorized:case-program
```

模板中的 ID 和内容均为占位结构，不是案例。
