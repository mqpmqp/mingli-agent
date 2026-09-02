# 梅花易数确定性排卦协议 v1

## 目标

相同原始输入与相同 `profile_id` 必须得到完全相同的本卦、互卦、变卦、动爻、体卦和用卦。不同起卦流派不得在运行时隐式混用。

固定状态：

```text
structure_status=deterministic_spec
interpretation_status=not_included
prediction_validity=not_evaluated
```

## 一、基础常量

八卦数序固定为：

| 数 | 卦 | 五行 | 三爻位（自下而上，阳=1、阴=0） |
|---:|---|---|---|
| 1 | 乾 | 金 | `111` |
| 2 | 兑 | 金 | `110` |
| 3 | 离 | 火 | `101` |
| 4 | 震 | 木 | `100` |
| 5 | 巽 | 木 | `011` |
| 6 | 坎 | 水 | `010` |
| 7 | 艮 | 土 | `001` |
| 8 | 坤 | 土 | `000` |

注意：表中字符串按“初爻方向在左”书写，即从下爻到上爻；任何代码实现都必须显式标注 `line_order=bottom_to_top`。

余数规则：

- 取卦数时，除以 8 余 0 按 8；
- 取动爻时，除以 6 余 0 按第六爻；
- 动爻从下往上数，初爻为 1，上爻为 6。

## 二、允许的数字起卦 profile

### 1. 两数合取动爻

```text
profile_id=meihua-numeric-two-sum@1.0.0
upper_trigram = normalize_mod(A, 8)
lower_trigram = normalize_mod(B, 8)
moving_line = normalize_mod(A + B, 6)
```

输入必须保存原始 `A`、`B` 及先后顺序。

### 2. 三数显式动爻

```text
profile_id=meihua-numeric-three-explicit@1.0.0
upper_trigram = normalize_mod(A, 8)
lower_trigram = normalize_mod(B, 8)
moving_line = normalize_mod(C, 6)
```

该 profile 是本项目为三数字人工起卦固定的工作流约定。它不能在客户只说“三个数”时自动推断，必须由客户明确确认：第一数取上卦、第二数取下卦、第三数取动爻。

### 3. 不允许的隐式切换

以下情况返回 `NEEDS_CONFIRMATION` 或 `INPUT_CONFLICT`：

- 同一组三个数字，既按“两数之和取动爻”又按“第三数取动爻”；
- 上下卦顺序在解释过程中互换；
- 应用只给出卦名，原始数字和 profile 不明；
- 先按一个 profile 发布判断，结果不理想后改用另一个 profile；
- 负数、小数、字符串拼接或笔画数等未经 profile 明确允许的输入。

V1 数字输入仅接受非负整数。

## 三、六爻结构编码

1. 下卦构成第 1—3 爻；
2. 上卦构成第 4—6 爻；
3. 六爻顺序固定为 `bottom_to_top`；
4. 本卦由下卦与上卦直接组合；
5. 变卦只翻转唯一动爻；
6. 其余五爻保持不变。

## 四、互卦算法

设本卦六爻自下而上为 `L1...L6`：

```text
下互 = L2, L3, L4
上互 = L3, L4, L5
互卦 = 上互 / 下互
```

互卦只表示中间结构，不自动等于第二个结果，也不改变原事件合同。

## 五、体用划分

- 动爻位于第 1—3 爻：下卦为用，上卦为体；
- 动爻位于第 4—6 爻：上卦为用，下卦为体。

V1 只输出“体与用是谁”以及五行关系，不把生克关系直接换算为概率或吉凶结论。

## 六、确定性结构输出

最小输出必须包含：

```text
profile_id
line_order
raw_inputs
upper_trigram
lower_trigram
primary_hexagram
mutual_hexagram
changed_hexagram
moving_line
body_trigram
use_trigram
body_element
use_element
canonical_payload_sha256
prediction_validity=not_evaluated
```

`canonical_payload_sha256` 用于发现结构记录不一致，不是数字签名，也不能证明输入来源真实。

## 七、合成结构夹具

输入：

```text
profile_id=meihua-numeric-three-explicit@1.0.0
A=60
B=70
C=50
```

计算：

```text
60 mod 8 -> 4 -> 震（上卦）
70 mod 8 -> 6 -> 坎（下卦）
50 mod 6 -> 2 -> 二爻动
```

六爻自下而上：

```text
坎 010 + 震 100 -> 010100
```

结果：

```text
本卦=雷水解
互卦=水火既济
变卦=雷地豫
动爻=二爻
体卦=震木
用卦=坎水
```

该夹具只验证排卦结构；不包含关于迁移、身份、时间或成败的预测。

## 八、当前不实现

- 公历自动换算农历、节气、月令和时支；
- 时间起卦的换日、真太阳时或地区时差政策；
- 物象、声音、文字和笔画的自动规范化；
- 多动爻；
- 旺衰、体党用党评分；
- 卦辞、爻辞、外应和应期自动解释；
- 自然语言吉凶输出。

这些内容需要独立来源审查和测试后才能增加新 profile，不能直接修改现有 profile 的语义。
