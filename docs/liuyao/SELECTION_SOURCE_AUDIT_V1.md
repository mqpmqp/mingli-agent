# 六爻事件合同与自动取用来源审计 v1

## 文档状态

本文只审计第三阶段第三切片所需的取用来源边界，覆盖通用六亲映射、用神两现、考试、传统婚姻与求孕方法。本文证明的是“上传资料中存在何种文字口径”，不是对六爻预测准确率的验证，也不授权生产使用。

固定边界：

```text
audit_status=review_only
source_profile_status=draft
source_profile_evidence_level=source_only
source_profile_human_reviewed=false
production_allowed=false
prediction_validity=not_evaluated
```

本次采用定向页级复核；没有对扫描本做全书 OCR。作者自报的应验、案例反馈、古例重释及未经独立样本支持的经验总结，均不能转换成概率、置信度或自动决胜权重。

## 来源登记与来源族

本文使用下列短标识：

| 标识 | 资料 | SHA-256 | 页码关系 | 来源角色 |
|---|---|---|---|---|
| `src_039` | 《周易预测宝典》（邵伟华） | `afa2cd2ad5acc09f3d7b4f4bb65f98d71f2199125ddef6ada84a0d114a626f79` | 本次命中页 PDF 页与印刷页相同 | 活动来源文本 |
| `src_037` | 《周易与预测学》（邵伟华） | `c00449b2a1d58da4da091a0078e580ad7657f015b3bed770131d11db158b4fb8` | PDF 页 = 印刷页 + 15 | 活动来源文本；扫描页经版面复核 |
| `src_040` | 《未知之门——邵伟华与周易预测索秘》（张志春） | `3e7a8c70fb0d4554f5b17d25bf50069c3366fd0e7aaecb79c097a8ee32dedb01` | PDF 页 = 印刷页 + 17 | 本切片不激活规则，仅可作范围审计 |

`src_039` 与 `src_037` 的章节次序、案例及本切片关键段落平行或近逐字相同，必须合并计为一个来源族：

```text
source_family_id=shaoweihua-liuyao-lineage
source_family_alias=F_SHAO_PARALLEL_TEXT
active_rule_source_family_count=1
empirical_validation_source_family_count=0
```

两个平行文本可以同时留下页码收据，但不得重复加权，也不得表述为两份独立验证。`src_040` 不参与本切片活动规则，因此不改变活动来源族数量。

## 证据分级

本审计使用与第二切片一致的证据等级：

```text
author_rule             作者直接陈述的规则、个人取法或方法边界
attributed_quote        作者明确归于《增删卜易》《卜筮正宗》等前人文字
author_case             作者提供并自行解释或反馈的案例
classic_reinterpretation 古例由作者重新解释
mixed_method_case       多种术数方法混用的案例
source_text_anomaly     原页存在错字、漏字或语义歧义
not_found               本次资料未找到可支持的通则
```

`author_case`、`classic_reinterpretation` 和 `mixed_method_case` 不能单独升级为通则；`attributed_quote` 只证明本书如何转述前人规则，不证明原典版本、现实有效性或跨题型适用性。

## 一、通用六亲映射

共同来源：

| 来源位置 | 等级 | 作用域 |
|---|---|---|
| `src_039:print163-164/pdf163-164` | `author_rule` | `general_object_relation_mapping` |
| `src_037:print179-180/pdf194-195` | `author_rule` | `general_object_relation_mapping` |

原页先区分“世爻为自己之身”与“用神为所测之事”，再按对象列出五类六亲。可编码的最小映射如下：

| 规则 ID | 来源支持的对象语义 | 候选 | 编码边界 |
|---|---|---|---|
| `SELF-TO-SHI` | 自己 | 世爻 | 世爻是主体选择器，不是第六种六亲。来源未给出代占时将他人自动改映射到世爻的通则。 |
| `PARENTS_GENERAL` | 父母、长辈、老师、文书、文章、书馆、文契等 | 父母 | 只生成对象关系候选；考试题须进入考试专项规则，不能仅因“文书”自动定父母。 |
| `OFFICER_GENERAL` | 功名、求官、官府、官长等 | 官鬼 | 原页中的婚姻用法必须进入后述传统异性婚姻范围，不能当成一般关系映射。 |
| `SIBLINGS_GENERAL` | 兄弟姐妹、同辈亲属、知交朋友 | 兄弟 | 不得扩展成所有竞争者、同事或社交关系。 |
| `WEALTH_GENERAL` | 妻、财物、货物、金银、钱粮、器物等 | 妻财 | “妻”是历史文本中的特定配偶角色，不能泛化为所有女性或所有伴侣。 |
| `DESCENDANTS_GENERAL` | 儿女、晚辈、医生医药、六畜等 | 子孙 | “医生医药”只可作为来源语义标签，不能生成诊断、疗效或健康结论。 |

运行时只能由已确认的规范化对象语义或显式关系覆盖触发这些候选。自由文本、姓名、代词或刻板印象不足以证明对象角色。

## 二、用神两现：来源偏好只形成收据

### 1. 来源条目

| 内容 | 来源位置 | 等级 | 作用域 |
|---|---|---|---|
| 旺相相对休囚、动相对静、不月破相对月破、不旬空相对旬空、不受伤相对受伤的取舍偏好 | `src_039:print173/pdf173`；`src_037:print189/pdf204` | `attributed_quote` | `same_relation_multiple_visible_candidates` |
| 两候选同动或同静时，参考近世、得生助或旺于月日 | `src_039:print174/pdf174`；`src_037:print190/pdf205` | `author_rule` | `same_relation_unresolved_after_basic_preferences` |
| 配套卦例 | `src_039:print173-175/pdf173-175`；`src_037:print189-191/pdf204-206` | `author_case` | `case_specific` |

可编码的来源偏好命中为：

```text
prefer_vigorous_over_weak
prefer_moving_over_static
prefer_not_month_broken
prefer_not_void
prefer_uninjured
prefer_nearer_shi
prefer_supported
prefer_vigorous_in_month_or_day
```

### 2. 不构成自动排序

这些文字没有建立条件之间的完备总排序。两个候选各自在不同条件上占优时，不能用规则声明顺序或程序加载顺序决定胜负。本项目固定：

```text
effect=source_preference_receipt_only
automatic_tiebreak=false
moving_line_auto_wins=false
```

即使某一候选命中“动”，也只能留下 `source_preference_hit`，不能因此自动成为最终用神。空、破、旺衰和当前力量必须消费第二切片有效性矩阵的收据，选择层不得另算一套；历法未确认时，不得生成依赖月、日或旬空的偏好命中。

书中的“多有应”“实践经验证明”等文字属于作者有效性声称，没有可审计的独立样本、对照或失败记录，不得转换为权重、概率或置信度。

## 三、考试与现代“考公”的范围

### 1. 官父双用

| 内容 | 来源位置 | 等级 |
|---|---|---|
| 升学以官印为主，父母为印与文书，官鬼为名并生父母 | `src_039:print242/pdf242`；`src_037:print259/pdf274` | `author_rule` |
| 文试官父两用，武试专看官星 | `src_039:print247/pdf247`；`src_037:print264/pdf279` | `author_rule` |

可编码为：

```text
cultural_or_written_exam -> relation_candidates=(官鬼,父母), ordered=false
martial_exam             -> relation_candidates=(官鬼)
```

“官父两用”不是两个来源互相矛盾，而是来源方法与“只能有一个 primary relation”的单选合同发生结构冲突。因此文试必须产生 `dual_relation_source_scope` 或 `relation_confirmation_required`，不能静默定为“官鬼主、父母辅”。

### 2. 现代“考公”不能直接等同古代题型

资料没有直接定义现代公务员考试，也没有说明应把其笔试、材料文书、面试、职位取得和任职结果压成同一个对象。事件合同至少应先区分：

- 笔试、文化或知识考核；
- 材料、证书或文书环节；
- 职位、任职或求官对象；
- 未分解的现代“考公”总问。

未分解的现代“考公”应返回 `modern_exam_scope_unresolved`，最多展示官鬼与父母两个来源候选，不自动决胜。金榜题名、具体分数、是否录取、排名和时间均不在本切片可编码范围。

## 四、传统异性婚恋映射范围

来源位置：

| 来源位置 | 等级 | 文本范围 |
|---|---|---|
| `src_039:print257/pdf257` | `author_rule` | 男女、夫妻、婚姻框架；男问女取妻财，女问男取官鬼 |
| `src_037:print275/pdf290` | `author_rule` | 与上条平行 |

仅在关系形态和角色方向均被显式确认时，可编码：

```text
traditional_heterosexual_marriage + male_subject_female_spouse -> 妻财
traditional_heterosexual_marriage + female_subject_male_spouse -> 官鬼
```

原页还谈及初婚者与已婚夫妻，但没有为缘分牵引、复联、复合、稳定等现代事件焦点分别建立不同用神。这些只能是工程事件维度，不是来源事实。

下列情况均不得自动应用这组映射：

- 同性关系或非二元身份；
- 性别、配偶角色或关系形态未确认；
- 仅凭姓名、称谓或代词推断性别与角色；
- 代占、第三人关系；
- 暧昧、普通亲密关系、复联或复合对象未明确等同于婚姻配偶。

范围不满足时应输出 `source_scope_not_covered`。系统可以接受用户显式关系覆盖，但必须标为人工覆盖，不能伪装成来源已经验证的映射。妻财与官鬼也不得被解释为性别本质、关系价值或吉凶高低。

“白头到老”、必成必散、贫富、相貌、贞操等断语不进入活动规则。

## 五、求孕中的胎爻／子孙方法冲突

### 1. 两种方法并存

| 内容 | 来源位置 | 等级 |
|---|---|---|
| 胎爻法与子孙法在使用中并存，作者说明自己通常采用子孙 | `src_039:print277/pdf277`；`src_037:print296/pdf311` | `author_rule` |
| 书中转述《增删卜易》以子孙为用 | 同上 | `attributed_quote` |
| 书中转述《卜筮正宗》以胎爻为用且不看子孙 | `src_039:print277-278/pdf277-278`；`src_037:print296-297/pdf311-312` | `attributed_quote` |

可编码的方法集合：

```text
method=children_relation -> relation=子孙
method=fetal_marker      -> selector=胎爻
author_preference=children_relation
default_method=null
requires_explicit_method_confirmation=true
automatic_resolution=false
```

作者个人偏好不能升级为两种方法之间的全局优先级。若当前结构模型没有胎爻计算能力，选择层必须保留：

```text
unconfirmed_method_selection_status=source_method_conflict
fetal_marker_selection_status=unsupported_method
unsupported_method_dependency=FETAL_MARKER_NOT_IMPLEMENTED
```

不得因实现缺少胎爻而静默退回子孙法，也不得把胎爻伪装成某一种六亲。

### 2. 医疗与生育结果排除

`conception_opportunity` 最多产生 `review_only` 的结构候选，不能输出是否已孕、是否能孕、受孕概率或成败结论。以下内容无论原页是否存在断语，均不进入活动规则：

- 流产、死胎、胎儿健康、孕妇健康和分娩安全；
- 胎儿性别、双胎、残疾或疾病；
- 生育能力、具体受孕日、孕周、预产期和分娩时点；
- 任何医疗诊断、治疗、用药或替代临床检查的建议。

`medical_confirmation`、`pregnancy_stability` 和 `medical_factors` 必须转入现实医疗证据或专业服务门禁，不执行六亲自动取用。

## 六、统一排除项与未发现项

来源档案应固定保留下列排除项：

```text
parallel_texts_do_not_count_as_independent_validation
author_success_claims_do_not_create_accuracy_weights
author_cases_do_not_create_universal_rules
moving_line_does_not_auto_break_ties
proxy_subject_mapping_not_found
modern_civil_service_equivalence_not_found
same_sex_and_nonbinary_relationship_mapping_not_found
relationship_focus_specific_use_mapping_not_found
medical_and_reproductive_outcome_claims_excluded
timing_probability_and_final_fortune_excluded
```

特别说明：

- 本次没有找到代占主体自动映射的可执行通则；代占必须由工程合同显式确认主体位置。
- 本次没有找到同性、非二元或不按传统夫妻角色组织的关系取用通则；“未找到”不表示这些关系无效，只表示资料不覆盖。
- 本次没有找到把现代考公无条件等同于官鬼、父母或其中固定主次的通则。
- 本次没有找到可将两现偏好转换为概率、置信度或固定数值权重的证据。
- 本切片不处理应期；所有具体日期、月份、出空、填实等时点推断留在后续独立切片，且仍须重新过来源与现实门禁。

## 七、实现约束摘要

来源档案只允许产生以下输出：

```text
relation_candidate
subject_selector_candidate
source_preference_receipt
source_scope_conflict
source_method_conflict
source_scope_not_covered
```

它不得直接产生：

```text
final_use_selection
event_success_or_failure
medical_or_reproductive_outcome
timing_candidate
probability_or_accuracy_claim
```

因此，本组资料足以支持“候选关系、来源偏好收据、范围冲突和方法冲突”，不足以支持无确认的自动唯一取用，更不足以支持成败、概率、应期或医疗判断。
