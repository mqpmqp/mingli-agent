from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .bazi import DeterministicBaziEngine
from .contracts.serialization import digest
from .delivery_contracts import (
    CaseInput,
    ConfidenceProfile,
    EvidenceQuality,
    InputValidation,
    PaidTier,
    validate_case_input,
)
from .errors import ChartCalculationError
from .phase19 import Phase19InputError, calculate_chenggu
from .renderer import DISCLAIMER, ensure_safe_text
from .rule_governance import (
    DomainRule,
    load_domain_rules,
    match_advice,
    production_rules,
)


PAID_SECTION_TITLES = (
    "资料确认",
    "核心结论和分层置信度",
    "前事校验",
    "当前核心矛盾",
    "当前主题深断",
    "时间窗口",
    "现实行动方案",
    "玄学辅助",
    "风险、反证和复盘节点",
)

_DOMAIN_LABELS = {
    "finance": "财运",
    "relationship": "感情",
    "exam_education": "考试与教育",
    "civil_service_and_public_institution": "考公考编",
    "career": "事业",
    "health": "健康",
    "fengshui": "风水",
    "migration": "迁移",
    "art_and_skill": "艺术与技能",
}
_CONFIDENCE_LABELS = {"high": "高", "medium": "中", "low": "低"}


@dataclass(frozen=True, slots=True)
class DeliverySection:
    title: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "content": self.content}


@dataclass(frozen=True, slots=True)
class DeterministicRuntimeReceipt:
    status: str
    engine: str
    facts: Mapping[str, object]
    warnings: tuple[str, ...]
    unsupported: tuple[str, ...]
    canonical_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "engine": self.engine,
            "facts": dict(self.facts),
            "warnings": list(self.warnings),
            "unsupported": list(self.unsupported),
            "canonical_hash": self.canonical_hash,
        }


@dataclass(frozen=True, slots=True)
class PaidDeliveryResult:
    case_id: str
    paid_tier: str
    render_intent: str
    domain: str
    validation: InputValidation
    runtime: DeterministicRuntimeReceipt
    confidence: ConfidenceProfile
    evidence_chain: tuple[str, ...]
    counterevidence: tuple[str, ...]
    rule_ids: tuple[str, ...]
    advice_ids: tuple[str, ...]
    optional_modules: tuple[str, ...]
    sections: tuple[DeliverySection, ...]
    evaluation_receipt: Mapping[str, object]
    rendered_text: str
    canonical_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "paid_tier": self.paid_tier,
            "render_intent": self.render_intent,
            "domain": self.domain,
            "validation": self.validation.to_dict(),
            "runtime": self.runtime.to_dict(),
            "confidence": self.confidence.to_dict(),
            "evidence_chain": list(self.evidence_chain),
            "counterevidence": list(self.counterevidence),
            "rule_ids": list(self.rule_ids),
            "advice_ids": list(self.advice_ids),
            "optional_modules": list(self.optional_modules),
            "sections": [section.to_dict() for section in self.sections],
            "evaluation_receipt": dict(self.evaluation_receipt),
            "rendered_text": self.rendered_text,
            "canonical_hash": self.canonical_hash,
        }


def build_confidence_profile(
    *,
    input_reliable: bool,
    algorithm_deterministic: bool,
    rule_statuses: Sequence[str],
    evidence_chain: Sequence[str],
    strong_reality_counterevidence: bool,
    external_variables: bool,
    event_data_complete: bool,
    action_prerequisites_met: bool,
) -> ConfidenceProfile:
    reasons: list[str] = []
    production_only = bool(rule_statuses) and all(
        status == "production" for status in rule_statuses
    )
    has_evidence = bool(evidence_chain)

    if input_reliable and algorithm_deterministic:
        chart = "high"
        reasons.append("输入可靠且排盘算法确定")
    else:
        chart = "low"
        if not input_reliable:
            reasons.append("时间、对象或命盘资料不完整")
        if not algorithm_deterministic:
            reasons.append("相关算法不可用或未进入确定性运行")

    if chart == "low" or not production_only or not has_evidence:
        interpretation = "low"
        if not production_only:
            reasons.append("规则未全部达到 production")
        if not has_evidence:
            reasons.append("缺少明确证据链")
    elif strong_reality_counterevidence or external_variables:
        interpretation = "medium"
        reasons.append("现实反证或外部变量限制解释强度")
    else:
        interpretation = "high"
        reasons.append("production 规则与证据链一致")

    if interpretation == "low" or not event_data_complete:
        event = "low"
        if not event_data_complete:
            reasons.append("事件所需现实资料不完整")
    elif strong_reality_counterevidence:
        event = "low"
        reasons.append("强现实反证优先于术数象意")
    elif external_variables or interpretation == "medium":
        event = "medium"
        reasons.append("事件结果受外部主体或制度变量影响")
    else:
        event = "high"

    if event == "low" or not action_prerequisites_met:
        action = "low"
        if not action_prerequisites_met:
            reasons.append("行动前置条件尚未满足")
    elif event == "medium" or interpretation == "medium":
        action = "medium"
    else:
        action = "high"

    return ConfidenceProfile(
        chart,
        interpretation,
        event,
        action,
        tuple(dict.fromkeys(reasons)),
    )


def _runtime_receipt(
    *,
    status: str,
    engine: str,
    facts: Mapping[str, object],
    warnings: Sequence[str] = (),
    unsupported: Sequence[str] = (),
) -> DeterministicRuntimeReceipt:
    body = {
        "status": status,
        "engine": engine,
        "facts": dict(facts),
        "warnings": list(warnings),
        "unsupported": list(unsupported),
    }
    return DeterministicRuntimeReceipt(
        status=status,
        engine=engine,
        facts=MappingProxyType(dict(facts)),
        warnings=tuple(warnings),
        unsupported=tuple(unsupported),
        canonical_hash=digest(
            {"record_type": "DeterministicRuntimeReceipt", "payload": body}
        ),
    )


def _run_deterministic_runtime(
    case: CaseInput,
    validation: InputValidation,
) -> DeterministicRuntimeReceipt:
    birth = case.birth
    if birth is None:
        return _runtime_receipt(
            status="degraded",
            engine="not_run",
            facts={},
            warnings=("birth_input_missing",),
            unsupported=("chart", "timeline", "event_prediction"),
        )
    if birth.source in {"image_confirmed", "text_confirmed"}:
        if not birth.has_confirmed_pillars:
            return _runtime_receipt(
                status="degraded",
                engine="confirmed-pillar-static-runtime",
                facts={},
                warnings=("image_chart_unconfirmed",),
                unsupported=("static_chart", "timeline", "event_prediction"),
            )
        return _runtime_receipt(
            status="degraded",
            engine="confirmed-pillar-static-runtime",
            facts={
                "pillars": dict(birth.pillars or {}),
                "source": birth.source,
                "confirmation_status": birth.confirmation_status,
            },
            warnings=("confirmed_pillars_static_only",),
            unsupported=("birth_metadata", "timeline", "true_solar_time"),
        )

    birth_missing = any(
        field_name.startswith("birth.") for field_name in validation.missing_fields
    )
    if birth_missing or any(
        error.startswith("invalid_birth") for error in validation.errors
    ):
        return _runtime_receipt(
            status="degraded",
            engine="bazi-deterministic",
            facts={},
            warnings=("birth_metadata_incomplete",),
            unsupported=("chart", "timeline", "event_prediction"),
        )
    try:
        chart = dict(DeterministicBaziEngine().calculate(birth.to_runtime_mapping()))
    except ChartCalculationError as exc:
        return _runtime_receipt(
            status="degraded",
            engine="bazi-deterministic",
            facts={},
            warnings=(f"chart_error:{exc.code}",),
            unsupported=("chart", "timeline", "event_prediction"),
        )
    status = "degraded" if case.divination is not None else "complete"
    warnings = (
        ("liuyao_engine_unavailable",) if case.divination is not None else ()
    )
    unsupported = ("liuyao_interpretation",) if case.divination is not None else ()
    return _runtime_receipt(
        status=status,
        engine="bazi-deterministic",
        facts={"chart": chart},
        warnings=warnings,
        unsupported=unsupported,
    )


def _domain_rules(domain: str) -> tuple[DomainRule, ...]:
    return tuple(
        rule
        for rule in production_rules(load_domain_rules())
        if rule.domain == domain
    )


def _counterevidence(
    domain: str,
    facts: Mapping[str, object],
) -> tuple[str, ...]:
    values: list[str] = []
    if domain == "relationship":
        married_values = {
            facts.get("other_party_status"),
            facts.get("other_party_marital_status"),
        }
        if "married" in married_values:
            values.append("对方已婚")
        if facts.get("other_party_new_relationship") is True or facts.get(
            "new_partner_present"
        ) is True:
            values.append("对方已有新关系")
        if facts.get("contact_status") == "blocked":
            values.append("联系渠道已被屏蔽")
        no_contact = facts.get("no_contact_months")
        if isinstance(no_contact, (int, float)) and not isinstance(no_contact, bool):
            if no_contact >= 12:
                values.append("长期失联")
        if facts.get("explicit_rejection") is True:
            values.append("已有明确拒绝")
        if facts.get("family_opposition") is True:
            values.append("家庭存在现实阻力")
        if facts.get("safety_risk") is True or facts.get(
            "legal_contact_restriction"
        ) is True:
            values.append("存在安全或法律边界")
    elif domain == "civil_service_and_public_institution":
        for key, label in (
            ("major_eligible", "专业资格不符"),
            ("age_eligible", "年龄资格不符"),
            ("degree_eligible", "学历资格不符"),
            ("hukou_eligible", "户籍资格不符"),
        ):
            if facts.get(key) is False:
                values.append(label)
    elif domain == "finance":
        if facts.get("cashflow_status") == "critical":
            values.append("现金流处于紧张状态")
        if facts.get("borrowing_for_ritual") is True:
            values.append("存在借款支付仪式的风险")
    elif domain == "health" and facts.get("symptoms"):
        values.append("存在需要医疗评估的症状")
    elif domain == "fengshui":
        if not facts.get("floor_plan_confirmed"):
            values.append("户型资料未确认")
        if not facts.get("compass_measurement_confirmed"):
            values.append("测量资料未确认")
    return tuple(dict.fromkeys(values))


def _event_data_complete(domain: str, facts: Mapping[str, object]) -> bool:
    requirements = {
        "finance": ("cashflow_status",),
        "relationship": ("contact_status", "other_party_status"),
        "exam_education": ("exam_scores", "exam_stage"),
        "civil_service_and_public_institution": (
            "exam_stage",
            "recruitment_target",
        ),
        "career": ("career_status", "target_positions"),
        "health": ("symptoms", "medical_assessment"),
        "fengshui": ("floor_plan_confirmed", "compass_measurement_confirmed"),
        "migration": ("migration_destination", "visa_status"),
        "art_and_skill": ("skill_level", "portfolio_status"),
    }
    return all(key in facts for key in requirements[domain])


def _strong_counterevidence(domain: str, facts: Mapping[str, object]) -> bool:
    if domain == "relationship":
        return any(
            (
                facts.get("other_party_status") == "married",
                facts.get("other_party_marital_status") == "married",
                facts.get("contact_status") == "blocked",
                facts.get("explicit_rejection") is True,
                facts.get("legal_contact_restriction") is True,
                facts.get("safety_risk") is True,
            )
        )
    if domain == "civil_service_and_public_institution":
        return any(
            facts.get(key) is False
            for key in ("major_eligible", "age_eligible", "degree_eligible")
        )
    if domain == "finance":
        return facts.get("cashflow_status") == "critical" or facts.get(
            "borrowing_for_ritual"
        ) is True
    if domain == "health":
        return bool(facts.get("symptoms")) and not facts.get("medical_assessment")
    return False


def _evidence_chain(
    case: CaseInput,
    runtime: DeterministicRuntimeReceipt,
    rules: Sequence[DomainRule],
) -> tuple[str, ...]:
    evidence: list[str] = []
    if runtime.facts:
        evidence.append(f"chart:{runtime.canonical_hash}")
    if case.reality.facts:
        prefix = (
            "reality:verified"
            if case.evidence_quality is EvidenceQuality.VERIFIED_REALITY
            else "reality:self-reported"
        )
        evidence.append(f"{prefix}:{digest(dict(case.reality.facts))}")
    evidence.extend(f"rule:{rule.canonical_hash}" for rule in rules)
    return tuple(evidence)


def _confidence_for(
    case: CaseInput,
    validation: InputValidation,
    runtime: DeterministicRuntimeReceipt,
    rules: Sequence[DomainRule],
    evidence_chain: Sequence[str],
    strong_counter: bool,
) -> ConfidenceProfile:
    critical_reasons = {
        "birth_input_missing",
        "birth_metadata_incomplete",
        "image_chart_unconfirmed",
    }
    input_reliable = (
        not validation.errors
        and not validation.missing_fields
        and not critical_reasons.intersection(validation.degradation_reasons)
    )
    algorithm_deterministic = runtime.engine in {
        "bazi-deterministic",
        "confirmed-pillar-static-runtime",
    } and bool(runtime.facts)
    external_variables = case.question_intent.domain in {
        "relationship",
        "civil_service_and_public_institution",
        "career",
        "migration",
    }
    event_complete = _event_data_complete(
        case.question_intent.domain, case.reality.facts
    )
    action_ready = bool(case.reality.facts) and not strong_counter
    return build_confidence_profile(
        input_reliable=input_reliable,
        algorithm_deterministic=algorithm_deterministic,
        rule_statuses=tuple(rule.status for rule in rules),
        evidence_chain=evidence_chain,
        strong_reality_counterevidence=strong_counter,
        external_variables=external_variables,
        event_data_complete=event_complete,
        action_prerequisites_met=action_ready,
    )


def _materials(case: CaseInput, validation: InputValidation) -> str:
    birth = case.birth
    lines: list[str] = []
    if birth is None:
        lines.append("未提供出生资料，本次不能进入命盘判断。")
    elif birth.source in {"image_confirmed", "text_confirmed"}:
        if birth.confirmation_status != "confirmed":
            lines.append("图片四柱尚未确认；本次只保留限制说明，不能进入时点推断。")
        else:
            pillars = "、".join((birth.pillars or {}).values())
            lines.append(
                f"四柱已由用户确认：{pillars}；因缺少完整出生元数据，只支持静态结构。"
            )
    elif any(item.startswith("birth.") for item in validation.missing_fields):
        missing = "、".join(
            item for item in validation.missing_fields if item.startswith("birth.")
        )
        lines.append(f"出生资料缺失：{missing}；系统已自动降级，不补写命盘事实。")
    else:
        lines.append("出生日期、时刻、地点、时区与历法已进入确定性校验。")
    if case.divination is not None:
        lines.append(
            "已收到六次结果、起卦时刻、地点与目标事件；仓库暂无可靠六爻引擎，因此不生成卦象结论。"
        )
    lines.append(f"现实资料字段：{len(case.reality.facts)} 项。")
    return "".join(lines)


def _confidence_text(confidence: ConfidenceProfile) -> str:
    return "；".join(
        (
            f"命盘置信度：{_CONFIDENCE_LABELS[confidence.chart_confidence]}",
            f"解释置信度：{_CONFIDENCE_LABELS[confidence.interpretation_confidence]}",
            f"事件置信度：{_CONFIDENCE_LABELS[confidence.event_confidence]}",
            f"行动置信度：{_CONFIDENCE_LABELS[confidence.action_confidence]}",
        )
    )


def _core_conclusion(
    case: CaseInput,
    confidence: ConfidenceProfile,
    counterevidence: Sequence[str],
) -> str:
    label = _DOMAIN_LABELS[case.question_intent.domain]
    body = [
        f"本次只回答{label}主题，不扩展到其他主题。",
        _confidence_text(confidence) + "。",
        "确定性排盘（同一规范化输入会得到同一结果）只提供结构事实，事件判断还要服从现实资料。",
    ]
    if counterevidence:
        body.append("现实边界优先：" + "、".join(counterevidence) + "。")
    body.append("成立条件：关键现实资料真实、相关前置条件持续满足。")
    body.append("反证：新增硬事实与当前判断冲突时，当前结论立即降级或撤回。")
    return "".join(body)


def _past_validation(case: CaseInput) -> str:
    if not case.reality.facts:
        return "尚无可独立核对的前事资料；不把泛化描述当作验证结果。"
    keys = "、".join(case.reality.facts)
    return (
        f"前事校验只采用用户提供的现实字段：{keys}。"
        "未提供独立记录的部分保持未验证，作者自述与付款记录不能升级为证据。"
    )


def _core_conflict(domain: str, facts: Mapping[str, object]) -> str:
    if domain == "relationship":
        return "核心矛盾是关系牵引与对方现实边界之间的差距；婚姻、失联、新关系和家庭条件优先。"
    if domain == "civil_service_and_public_institution":
        return "核心矛盾是主观期待与招录资格、成绩基线、岗位竞争之间的差距。"
    if domain == "exam_education":
        return "核心矛盾是目标成绩与当前成绩、练习反馈和复习时间之间的差距。"
    if domain == "finance":
        return "核心矛盾是收入期待与现金流、风险承受和预算纪律之间的差距。"
    if domain == "career":
        return "核心矛盾是发展期待与岗位资格、可验证成果及外部机会之间的差距。"
    if domain == "health":
        return "核心矛盾是文化辅助期待与专业医疗评估、作息和环境因素之间的边界。"
    if domain == "fengshui":
        return "核心矛盾是空间诉求与户型、测量、用途及建筑安全资料是否完整。"
    if domain == "migration":
        return "核心矛盾是迁移愿望与签证、预算、语言、住房及工作准备之间的差距。"
    return "核心矛盾是天赋期待与训练量、作品反馈及长期投入之间的差距。"


def _deep_analysis(
    domain: str,
    facts: Mapping[str, object],
    counterevidence: Sequence[str],
) -> str:
    counter = "、".join(counterevidence) or "尚未发现已核验的强现实反证"
    if domain == "relationship":
        return (
            "缘分牵引：只表示关系议题仍被关注，不能覆盖现实状态。"
            f"复联可能：先看联系渠道和对方边界；当前反证为{counter}。"
            "复合可能：成立条件是双方仍有意愿且分手根因可处理；拒绝、婚姻或安全边界构成反证。"
            "稳定可能：取决于沟通、信任、家庭与距离方案，不由单一象意决定。"
        )
    if domain == "civil_service_and_public_institution":
        return (
            "体制适配度：结合规则环境偏好、履历和长期工作方式评估。"
            "上岸可能：先核验资格、成绩基线和岗位竞争，只能形成条件性判断。"
            "考试运：作为状态提示，不替代模考结果。"
            "岗位方向：按专业、学历、地区、职责和竞争度筛选。"
            "备考策略：建立模考基线、错题复盘和面试训练。"
            "文昌与功名辅助：只作低成本文化辅助，录取仍以官方流程为准。"
        )
    layers = {
        "finance": "现金流：先确认收支和应急金。守财边界：先设预算与风险上限。收入与风险：不把文化象征当作收益依据。现实行动：用可核对账目复盘。",
        "exam_education": "基础成绩：先记录真实分数。考试状态：只看可观察趋势。学习策略：以计时练习和错题反馈为主。文昌辅助：只作为学习启动提醒。",
        "career": "岗位匹配：按资格和成果核验。发展矛盾：区分内部能力与外部机会。面试签约：准备证据并审阅条款。现实行动：设置投递和复盘节点。",
        "health": "症状边界：不作诊断。医疗优先：症状由合格医疗人员评估。作息压力：记录可观察变化。安康辅助：只用于放松和环境整理。",
        "fengshui": "资料完整度：户型和测量未齐时停止方向判断。居住问题：先区分安全、采光、通风和动线。安全布局：遵守建筑与消防规范。复核条件：补齐资料再评估。",
        "migration": "目标地区：核对真实政策。签证资格：以官方资料为准。语言与预算：建立可执行基线。迁移节奏：按申请节点复盘。",
        "art_and_skill": "技能基础：以作品和练习记录为准。练习反馈：需要外部评价。作品路径：分阶段迭代。阶段复盘：比较版本而非依赖象意。",
    }
    return layers[domain]


def _review_point(case: CaseInput) -> str:
    if case.review_checkpoint is None:
        return "资料补齐或现实状态变化后复盘"
    criteria = "、".join(case.review_checkpoint.criteria)
    return f"{case.review_checkpoint.review_at}，按{criteria}复盘"


def _time_window(case: CaseInput) -> str:
    return (
        "当前没有经过前向校准的具体日期依据，因此不提供具体日期。"
        "观察窗口应绑定现实事件和资料更新；复盘点："
        + _review_point(case)
        + "。"
    )


def _actions(domain: str) -> str:
    actions = {
        "finance": ("建立四周现金流表", "设置预算与风险上限", "每周核对实际收支"),
        "relationship": ("核对对方婚恋与联系边界", "只做一次尊重式沟通", "按回应更新判断"),
        "exam_education": ("记录当前成绩", "安排计时练习", "按错题类型调整复习"),
        "civil_service_and_public_institution": ("核验官方资格", "建立岗位筛选表", "持续模考和面试训练"),
        "career": ("整理可验证成果", "筛选真实岗位", "模拟面试并审阅合同"),
        "health": ("记录症状", "按紧急程度就医", "在专业建议下调整作息"),
        "fengshui": ("先排除安全问题", "补齐户型与测量", "从通风照明和动线做低风险调整"),
        "migration": ("查官方政策", "核验签证与预算", "准备住房工作和返程方案"),
        "art_and_skill": ("确定作品目标", "记录练习", "获取反馈并比较版本"),
    }
    return "；".join(f"{index}. {item}" for index, item in enumerate(actions[domain], 1)) + "。"


def _advice_text(domain: str, facts: Mapping[str, object]) -> tuple[str, tuple[str, ...]]:
    rules = match_advice(domain, facts)
    blocks: list[str] = []
    for rule in rules:
        required = "、".join(rule.required_real_world_actions)
        blocks.append(
            f"{rule.recommended_action}现实动作：{required}；频次上限：{rule.frequency_cap}；预算上限：{rule.budget_cap}。"
        )
    blocks.append("这些内容只作传统文化辅助，不替代现实决策或专业服务。")
    return "".join(blocks), tuple(rule.advice_id for rule in rules)


def _bone_weight_text(case: CaseInput) -> tuple[str, tuple[str, ...]]:
    if not case.question_intent.bone_weight_requested:
        return "", ()
    birth = case.birth
    if birth is None or not birth.birth_date or not birth.birth_time or not birth.calendar:
        return "骨重模块已由用户明确点名，但出生日期、时刻或历法不足，未执行计算。", ("bone_weight",)
    try:
        result = calculate_chenggu(
            {
                "calendar": birth.calendar,
                "birth_date": birth.birth_date,
                "birth_time": birth.birth_time,
                "is_leap_month": birth.is_leap_month,
            }
        )
    except Phase19InputError:
        return "骨重模块已由用户明确点名，但输入未通过计算边界，未生成结果。", ("bone_weight",)
    return (
        f"骨重（明确点名后启用）：{result.display_weight}；仅是传统文化算法，不含歌诀，不作为事件证据。",
        ("bone_weight",),
    )


def _risk_review(
    case: CaseInput,
    counterevidence: Sequence[str],
) -> str:
    counter = "、".join(counterevidence) or "现实资料不足或后续出现冲突事实"
    return (
        "成立条件：输入继续可靠、现实前提没有实质变化。"
        f"反证：{counter}。"
        f"复盘点：{_review_point(case)}；到点前不结算前向测试。"
    )


def _paid_sections(
    case: CaseInput,
    validation: InputValidation,
    confidence: ConfidenceProfile,
    counterevidence: Sequence[str],
    advice_text: str,
    bone_text: str,
) -> tuple[DeliverySection, ...]:
    metaphysical = advice_text + (bone_text if not bone_text else " " + bone_text)
    contents = (
        _materials(case, validation),
        _core_conclusion(case, confidence, counterevidence),
        _past_validation(case),
        _core_conflict(case.question_intent.domain, case.reality.facts),
        _deep_analysis(
            case.question_intent.domain, case.reality.facts, counterevidence
        ),
        _time_window(case),
        _actions(case.question_intent.domain),
        metaphysical,
        _risk_review(case, counterevidence),
    )
    return tuple(
        DeliverySection(title, content)
        for title, content in zip(PAID_SECTION_TITLES, contents, strict=True)
    )


def _follow_up_sections(
    case: CaseInput,
    confidence: ConfidenceProfile,
    counterevidence: Sequence[str],
    advice_text: str,
    bone_text: str,
) -> tuple[DeliverySection, ...]:
    topic = _DOMAIN_LABELS[case.question_intent.domain]
    auxiliary = advice_text + (bone_text if not bone_text else " " + bone_text)
    return (
        DeliverySection(
            "续问结论",
            f"本次只续答{topic}新增范围。" + _core_conclusion(case, confidence, counterevidence),
        ),
        DeliverySection("续问现实行动", _actions(case.question_intent.domain)),
        DeliverySection("玄学辅助", auxiliary),
        DeliverySection("复盘节点", _risk_review(case, counterevidence)),
    )


def _private_sections(
    case: CaseInput,
    validation: InputValidation,
    confidence: ConfidenceProfile,
    counterevidence: Sequence[str],
    advice_text: str,
) -> tuple[DeliverySection, ...]:
    return (
        DeliverySection("资料确认", _materials(case, validation)),
        DeliverySection("核心结论", _core_conclusion(case, confidence, counterevidence)),
        DeliverySection("现实行动", _actions(case.question_intent.domain)),
        DeliverySection("玄学辅助", advice_text),
        DeliverySection("风险与复盘", _risk_review(case, counterevidence)),
    )


def _comment_sections(
    case: CaseInput,
    confidence: ConfidenceProfile,
    counterevidence: Sequence[str],
) -> tuple[DeliverySection, ...]:
    return (
        DeliverySection("简要结论", _core_conclusion(case, confidence, counterevidence)),
        DeliverySection("现实提醒", _actions(case.question_intent.domain)),
    )


def _render(sections: Sequence[DeliverySection]) -> str:
    body = "\n\n".join(f"## {section.title}\n{section.content}" for section in sections)
    rendered = body.replace(DISCLAIMER, "").strip() + "\n\n" + DISCLAIMER
    ensure_safe_text(rendered)
    return rendered


def _evaluation_receipt(
    case: CaseInput,
    rule_ids: Sequence[str],
) -> Mapping[str, object]:
    due_at = (
        case.review_checkpoint.review_at if case.review_checkpoint is not None else None
    )
    return MappingProxyType(
        {
            "status": "pending_forward_test",
            "due_at": due_at,
            "rule_ids": list(rule_ids),
            "result": None,
            "prediction_validity": "not_evaluated",
            "settlement_policy": "due_at_before_settlement",
        }
    )


def run_paid_delivery(raw: CaseInput | Mapping[str, object]) -> PaidDeliveryResult:
    case = raw if isinstance(raw, CaseInput) else CaseInput.from_mapping(raw)
    validation = validate_case_input(case)
    runtime = _run_deterministic_runtime(case, validation)
    rules = _domain_rules(case.question_intent.domain)
    evidence_chain = _evidence_chain(case, runtime, rules)
    counterevidence = _counterevidence(
        case.question_intent.domain, case.reality.facts
    )
    strong_counter = _strong_counterevidence(
        case.question_intent.domain, case.reality.facts
    )
    confidence = _confidence_for(
        case,
        validation,
        runtime,
        rules,
        evidence_chain,
        strong_counter,
    )
    advice_text, advice_ids = _advice_text(
        case.question_intent.domain, case.reality.facts
    )
    bone_text, optional_modules = _bone_weight_text(case)

    if case.question_intent.render_intent == "follow_up":
        sections = _follow_up_sections(
            case, confidence, counterevidence, advice_text, bone_text
        )
    elif case.paid_tier is PaidTier.COMMENT:
        sections = _comment_sections(case, confidence, counterevidence)
    elif case.paid_tier is PaidTier.PRIVATE:
        sections = _private_sections(
            case, validation, confidence, counterevidence, advice_text
        )
    else:
        sections = _paid_sections(
            case,
            validation,
            confidence,
            counterevidence,
            advice_text,
            bone_text,
        )

    rendered_text = _render(sections)
    rule_ids = tuple(rule.rule_id for rule in rules)
    evaluation_receipt = _evaluation_receipt(case, rule_ids)
    body = {
        "case_id": case.case_id,
        "paid_tier": case.paid_tier.value,
        "render_intent": case.question_intent.render_intent,
        "domain": case.question_intent.domain,
        "validation": validation.to_dict(),
        "runtime": runtime.to_dict(),
        "confidence": confidence.to_dict(),
        "evidence_chain": list(evidence_chain),
        "counterevidence": list(counterevidence),
        "rule_ids": list(rule_ids),
        "advice_ids": list(advice_ids),
        "optional_modules": list(optional_modules),
        "sections": [section.to_dict() for section in sections],
        "evaluation_receipt": dict(evaluation_receipt),
        "rendered_text": rendered_text,
    }
    return PaidDeliveryResult(
        case_id=case.case_id,
        paid_tier=case.paid_tier.value,
        render_intent=case.question_intent.render_intent,
        domain=case.question_intent.domain,
        validation=validation,
        runtime=runtime,
        confidence=confidence,
        evidence_chain=evidence_chain,
        counterevidence=counterevidence,
        rule_ids=rule_ids,
        advice_ids=advice_ids,
        optional_modules=optional_modules,
        sections=sections,
        evaluation_receipt=evaluation_receipt,
        rendered_text=rendered_text,
        canonical_hash=digest(
            {"record_type": "PaidDeliveryResult", "payload": body}
        ),
    )
