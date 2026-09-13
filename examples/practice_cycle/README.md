# 离线合成工作类闭环

以下文件均为人为编写的 synthetic 工程夹具，无真人信息，不代表排盘结果或有预测效果的规则。入口复用现有 TrainingStore 和 prediction freeze；不访问网络、模型、排盘或生产服务。使用仓库已有 Python 环境执行。

在仓库根目录的 PowerShell 中运行：

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
$practiceStore = Join-Path ([System.IO.Path]::GetTempPath()) ('mingli-practice-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B -m mingli.cli training practice-run --input examples/practice_cycle/run.json --store $practiceStore --synthetic
.\.venv\Scripts\python.exe -B -m mingli.cli training practice-feedback --input examples/practice_cycle/feedback.json --store $practiceStore --synthetic
.\.venv\Scripts\python.exe -B -m mingli.cli training practice-replay --input examples/practice_cycle/replay.json --store $practiceStore --synthetic
.\.venv\Scripts\python.exe -B -m mingli.cli training practice-compare --input examples/practice_cycle/compare.json --store $practiceStore --synthetic
```

每次复现使用新的临时 store；重复 run_id 或反馈 id 会被拒绝，不覆盖记录。可使用现有 `mingli training show --case-id person:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb --store $practiceStore --synthetic` 查看保存结果。主观体验沿用已有 UserFeedback 追加在 `feedback/`，claim 结果沿用 OutcomeObservation 追加在 `outcomes/`，原预测存在 `runs/`。二者都绑定原 run；UserFeedback 明确不计准确率，合成 outcome 也不计真人准确率。本轮不引入第二套案例存储。

首步基线输出包含 GIVEN 已婚/在职两项和一条工作 inference，客户文本为：

> 你在2026年10月可能有机会收到岗位面谈安排。
>
> 仅供文化研究与娱乐参考。

重放候选保持同一问题、GIVEN 和 `as_of`，只替换成新版本的合成规则夹具与结构化判断；候选文本为“你在2026年10月可能收到一次岗位面谈安排，结果以正式通知为准。”。

评论版与付费版使用同一 inference 原文，仅改变段落间距。GIVEN 留在结构化底稿而不伪装成命中。规则夹具必须逐条支持原文、时间窗口、置信度和所需事实；这里的支持仅用于合成契约测试，不是命理应期依据的真实性认证。没有可支持判断时会返回具体错误。

示例比较预期：工程同一可见输入=true；synthetic 基线独立命中=1，候选=0/缺反馈=1，GIVEN 排除=2。基线反馈不会转移给候选追认命中。比较回执显式列出两份 run、规则版本及冻结预测哈希。真人合格样本=0、accuracy/metrics=null、status=not_evaluated。`release_hold=ACTIVE`、`commercial_release_hold=ACTIVE`、`prediction_validity=not_evaluated`。

工程报告分别给出 `time_consistency`、`given_not_scored`、`original_snapshot_not_overwritten`、`feedback_hidden_from_replay`、`normal_flow_completed`，本例均为 true。这些值由当前冻结记录重算的窗口、来源白名单、GIVEN 排除数、快照及反馈绑定和运行状态得出；不证明历史发布或现实预测有效。

基线与候选的产品报告分别保留全部输出；两者均为 `answered_current_question=true`、`unsupported_detail_count=0`、`over_refusal=false`、`manual_rewrite_amount=null`，有限空话检查从基线 `template_or_vague_phrase_count=1` 降至候选 0，因此只报告 `improvement.status=machine_checks_improved`。这些是工作主题词、逐条夹具支持、重复文本与有限空话词表的确定性检查，不替代人工语义审查；`human_quality_review` 仍为 `not_evaluated`。

真人结果另列 `due_with_feedback`、`not_due`、`lost_to_followup`、`unverifiable`、`refused`、`missing`，本例均为 0，并明确 `data_source=none`。这些 0 表示本轮没有真人输入，不能解读为观察到零失访、零拒答或零错误。

`practice-replay` 只能在同一冻结问题、GIVEN 和 `as_of` 上注册新 run_id/规则版本；可成对提供新的 `bases`/`claims`，两者仍须通过原截止点、时间、依据和安全校验。它不读取已登记反馈、不自动学习反馈，也不允许通过标题或额外字段注入结果。同一个案例后续必须走 replay，不能再次 practice-run 塞入反馈后资料并将其回填为旧时间。比较保留两份完整客户文本；所有样本在 development，不可充当独立留出集。跨人物或不同可见输入的比较会被拒绝。

时间仅来自显式带时区的 as_of、资料 available_at、recorded_at 和反馈 submitted_at。支持明确年月、日期或日期区间，以及“现在到今年X月”“回顾YYYY年X月”；其他时间说法应先明确，不能猜测或顺延年份。例如 as_of=2026-09-13 时“现在到今年五月”作为 future 返回 EXPIRED_FUTURE_WINDOW，回顾2026年5月可放行。时间字段与原文都经过检查。

recorded_at 和 freeze_timestamp 是调用者提供的合成时间，original_published_at=null、historical_prepublication_verified=false；本次生成的哈希不能证明历史上已事先发布。原 run 独占创建，后续反馈及版本不改变其原文、窗口、规则版本或哈希。重复/冲突反馈按同一 claim 汇总，冲突不选有利结果。合成 hit 是夹具标签，不是独立核验的现实结果。

验证：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_practice_cycle.py tests/test_real_case_learning_v2.py tests/test_product_training_loop.py -q
```

这组检查均使用本地合成输入和临时存储。未实现真人接入、自由自然语言时间解析、通用语义事实识别、自动命理规则推导、真人准确率评估或产品发布。
