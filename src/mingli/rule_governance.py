from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import TypeVar

from .contracts.serialization import canonical_json, digest


RULE_LIFECYCLE_STATUSES = (
    "raw",
    "draft",
    "reviewed",
    "production",
    "rejected",
    "pending_forward_test",
)
RULE_DOMAINS = (
    "finance",
    "relationship",
    "exam_education",
    "civil_service_and_public_institution",
    "career",
    "health",
    "fengshui",
    "migration",
    "art_and_skill",
)

_PROHIBITED_CLAIMS = (
    "包上岸",
    "保证复合",
    "保证发财",
    "医疗替代",
    "借钱做仪式",
)
_SCAM_RED_FLAGS = (
    "要求借钱或使用消费贷支付",
    "用灾祸恐吓并要求追加项目",
    "承诺录取、复合、发财或治病结果",
    "拒绝说明价格、次数或退出条件",
)


class RuleGovernanceError(ValueError):
    """Raised when a rule catalog cannot safely enter the paid runtime."""


@dataclass(frozen=True, slots=True)
class RuleReview:
    reviewer: str
    reviewed_at: str
    decision_id: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DomainRule:
    rule_id: str
    domain: str
    status: str
    triggers: tuple[str, ...]
    conclusions: tuple[str, ...]
    source_refs: tuple[str, ...]
    applicability: tuple[str, ...]
    counterexamples: tuple[str, ...]
    review: RuleReview
    reality_priority: bool = True

    @property
    def canonical_hash(self) -> str:
        return digest({"record_type": "DomainRule", "payload": self.to_dict()})

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "domain": self.domain,
            "status": self.status,
            "triggers": list(self.triggers),
            "conclusions": list(self.conclusions),
            "source_refs": list(self.source_refs),
            "applicability": list(self.applicability),
            "counterexamples": list(self.counterexamples),
            "review": self.review.to_dict(),
            "reality_priority": self.reality_priority,
        }


@dataclass(frozen=True, slots=True)
class AdviceRule:
    advice_id: str
    domain: str
    triggers: tuple[str, ...]
    contraindications: tuple[str, ...]
    required_inputs: tuple[str, ...]
    metaphysical_rationale: str
    real_world_problem: str
    recommended_action: str
    execution_steps: tuple[str, ...]
    frequency_cap: str
    budget_cap: str
    required_real_world_actions: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    scam_red_flags: tuple[str, ...]
    evidence_status: str
    status: str
    source_refs: tuple[str, ...]
    applicability: tuple[str, ...]
    counterexamples: tuple[str, ...]
    review: RuleReview

    @property
    def canonical_hash(self) -> str:
        return digest({"record_type": "AdviceRule", "payload": self.to_dict()})

    def to_dict(self) -> dict[str, object]:
        return {
            "advice_id": self.advice_id,
            "domain": self.domain,
            "triggers": list(self.triggers),
            "contraindications": list(self.contraindications),
            "required_inputs": list(self.required_inputs),
            "metaphysical_rationale": self.metaphysical_rationale,
            "real_world_problem": self.real_world_problem,
            "recommended_action": self.recommended_action,
            "execution_steps": list(self.execution_steps),
            "frequency_cap": self.frequency_cap,
            "budget_cap": self.budget_cap,
            "required_real_world_actions": list(self.required_real_world_actions),
            "prohibited_claims": list(self.prohibited_claims),
            "scam_red_flags": list(self.scam_red_flags),
            "evidence_status": self.evidence_status,
            "status": self.status,
            "source_refs": list(self.source_refs),
            "applicability": list(self.applicability),
            "counterexamples": list(self.counterexamples),
            "review": self.review.to_dict(),
        }


_REVIEW = RuleReview(
    reviewer="mingli-v2-local-contract-review",
    reviewed_at="2026-08-29",
    decision_id="MINGLI_V2_REALITY_FIRST_SAFETY_CONTRACT",
)

_DOMAIN_LAYERS = {
    "finance": ("现金流", "守财边界", "收入与风险", "现实行动"),
    "relationship": ("缘分牵引", "复联可能", "复合可能", "稳定可能"),
    "exam_education": ("基础成绩", "考试状态", "学习策略", "文昌辅助"),
    "civil_service_and_public_institution": (
        "体制适配度",
        "上岸可能",
        "考试运",
        "岗位方向",
        "备考策略",
        "文昌与功名辅助",
    ),
    "career": ("岗位匹配", "发展矛盾", "面试签约", "现实行动"),
    "health": ("症状边界", "医疗优先", "作息压力", "安康辅助"),
    "fengshui": ("资料完整度", "居住问题", "安全布局", "复核条件"),
    "migration": ("目标地区", "签证资格", "语言与预算", "迁移节奏"),
    "art_and_skill": ("技能基础", "练习反馈", "作品路径", "阶段复盘"),
}


def _domain_source(domain: str) -> tuple[str, ...]:
    if domain == "relationship":
        implementation = "src/mingli/phase17.py#relationship_reunion"
    elif domain == "civil_service_and_public_institution":
        implementation = "src/mingli/phase17.py#career_exam"
    else:
        implementation = "src/mingli/phase16.py#domain-contracts"
    return (
        implementation,
        "MINGLI_V2_FULL_UPGRADE_SPEC.md#专题规则包",
        "CONFIDENCE_AND_COUNTEREVIDENCE.md#现实反证优先",
    )


def load_domain_rules() -> tuple[DomainRule, ...]:
    """Return local safety/decision scaffolds, not empirical prediction claims."""

    rules: list[DomainRule] = []
    for domain in RULE_DOMAINS:
        rules.append(
            DomainRule(
                rule_id=f"domain:{domain}:reality-first",
                domain=domain,
                status="production",
                triggers=("domain_selected",),
                conclusions=_DOMAIN_LAYERS[domain],
                source_refs=_domain_source(domain),
                applicability=(
                    "仅用于用户明确选择的专题",
                    "必须同时呈现条件、反证与现实行动",
                ),
                counterexamples=(
                    "现实资料缺失时不能给出事件性强结论",
                    "已核验现实事实与象意冲突时以现实事实为准",
                ),
                review=_REVIEW,
            )
        )
    return tuple(rules)


def _advice(
    advice_id: str,
    domain: str,
    *,
    triggers: tuple[str, ...] = ("domain_selected",),
    contraindications: tuple[str, ...] = (),
    required_inputs: tuple[str, ...] = ("question_intent.domain",),
    metaphysical_rationale: str,
    real_world_problem: str,
    recommended_action: str,
    execution_steps: tuple[str, ...],
    required_real_world_actions: tuple[str, ...],
    frequency_cap: str = "最多一次设置、每月复核一次",
    budget_cap: str = "只用现有物品或小额可支配预算；不得借款",
    applicability: tuple[str, ...] = ("用户接受传统文化辅助",),
    counterexamples: tuple[str, ...] = ("用户不接受仪式时只保留现实行动",),
) -> AdviceRule:
    return AdviceRule(
        advice_id=advice_id,
        domain=domain,
        triggers=triggers,
        contraindications=contraindications,
        required_inputs=required_inputs,
        metaphysical_rationale=metaphysical_rationale,
        real_world_problem=real_world_problem,
        recommended_action=recommended_action,
        execution_steps=execution_steps,
        frequency_cap=frequency_cap,
        budget_cap=budget_cap,
        required_real_world_actions=required_real_world_actions,
        prohibited_claims=_PROHIBITED_CLAIMS,
        scam_red_flags=_SCAM_RED_FLAGS,
        evidence_status="traditional_culture_only",
        status="production",
        source_refs=(
            "METAPHYSICAL_ADVICE_GOVERNANCE.md#主题映射",
            "AGENTS.md#安全边界",
        ),
        applicability=applicability,
        counterexamples=counterexamples,
        review=_REVIEW,
    )


def load_advice_rules() -> tuple[AdviceRule, ...]:
    rules = (
        _advice(
            "advice:finance:cashflow-and-space",
            "finance",
            metaphysical_rationale="传统财位与开市择时只作为整理注意力的文化提示。",
            real_world_problem="现金流、预算纪律与交易准备需要先被看见。",
            recommended_action="先做守财与现金流盘点；如需文化辅助，可整理工作区财位并在开市前复核计划。",
            execution_steps=("列出未来四周收支", "清理工作区杂物", "开市前再次检查预算上限"),
            required_real_world_actions=("建立现金流表", "设置不可突破的损失和预算边界"),
        ),
        _advice(
            "advice:finance:explicit-wealth-repository",
            "finance",
            triggers=("explicit_wealth_repository_request",),
            contraindications=("cashflow_status=critical", "borrowing_for_ritual=true"),
            required_inputs=("explicit request", "cashflow_status", "discretionary_budget"),
            metaphysical_rationale="补财库与招财属于传统民俗象征，不是收入或投资结果证据。",
            real_world_problem="用户希望以一次性文化动作建立储蓄提醒。",
            recommended_action="仅在明确点名且预算无压力时，可做一次低成本补财库或招财象征，并同步设置自动储蓄。",
            execution_steps=("先确认不借款", "限定一次性预算", "完成后启动自动储蓄"),
            required_real_world_actions=("保留应急金", "拒绝任何追加收费"),
            frequency_cap="同一目标最多一次，不做连续追加",
        ),
        _advice(
            "advice:finance:ritual-decline",
            "finance",
            triggers=("cashflow_critical_or_borrowing",),
            contraindications=("cashflow_status=critical", "borrowing_for_ritual=true"),
            metaphysical_rationale="现实财务安全高于任何传统仪式。",
            real_world_problem="现金流紧张或准备借款支付文化服务。",
            recommended_action="当前不建议具体仪式；先停止新增支出并处理债务与基本生活现金流。",
            execution_steps=("取消仪式支出", "列出到期债务", "联系正规财务或公益咨询"),
            required_real_world_actions=("不得借钱支付", "优先基本生活与债务安排"),
            frequency_cap="不执行仪式",
            budget_cap="零仪式支出",
            applicability=("现金流紧张或出现借款意图",),
            counterexamples=("财务恢复后仍需重新评估，不自动转为推荐",),
        ),
        _advice(
            "advice:relationship:communication-and-space",
            "relationship",
            metaphysical_rationale="姻缘、桃花与沟通择时只用于提醒关系边界和沟通准备。",
            real_world_problem="关系推进取决于双方状态、联系意愿和冲突修复。",
            recommended_action="先确认对方边界；可用一次沟通择时和卧室整理作为自我准备，不以桃花或姻缘仪式替代沟通。",
            execution_steps=("核对婚恋与联系状态", "写下单次沟通目标", "整理卧室并移除旧关系刺激物"),
            required_real_world_actions=("尊重拒绝与失联边界", "处理分手根因"),
            contraindications=("other_party_married", "blocked", "safety_risk"),
        ),
        _advice(
            "advice:exam:study-station",
            "exam_education",
            metaphysical_rationale="启文昌、文昌祈福和开笔属于学习启动的文化仪式。",
            real_world_problem="成绩改善依赖可测量的练习、反馈和稳定学习环境。",
            recommended_action="可做一次低成本启文昌或开笔，并把学习位整理成固定复习区。",
            execution_steps=("记录当前成绩", "整理学习位", "开笔后完成首个计时练习"),
            required_real_world_actions=("建立错题复盘", "每周做一次计时测验"),
        ),
        _advice(
            "advice:civil-service:wenchang-merit",
            "civil_service_and_public_institution",
            metaphysical_rationale="文昌功名和启文昌助功名只作为备考纪律的文化锚点。",
            real_world_problem="录取受资格、岗位竞争、笔试、面试与招录规则共同影响。",
            recommended_action="可做一次低成本文昌功名辅助，同时以岗位筛选、模考和面试训练为主线。",
            execution_steps=("核验招录资格", "建立岗位表", "完成一次模考", "设置复盘日期"),
            required_real_world_actions=("以官方公告为准", "保留备选岗位", "持续模考与面试训练"),
        ),
        _advice(
            "advice:career:interview-and-contract",
            "career",
            metaphysical_rationale="事业功名、官禄、贵人与择时只用于集中准备。",
            real_world_problem="求职和晋升依赖岗位匹配、证据材料、沟通与合同条款。",
            recommended_action="可用一次面试或签约择时作为准备节点，并先完成简历证据、模拟面试和合同审阅。",
            execution_steps=("整理三项可验证成果", "完成模拟面试", "逐条核对合同"),
            required_real_world_actions=("核验雇主与岗位", "重要合同咨询专业人士"),
        ),
        _advice(
            "advice:health:medical-first",
            "health",
            metaphysical_rationale="安康、静心与净宅只可用于放松和环境整理。",
            real_world_problem="症状需要医疗评估，压力和居住环境只能作为辅助因素。",
            recommended_action="医疗评估优先；安康、静心或净宅只能作为不延误就医的低成本辅助。",
            execution_steps=("记录症状与持续时间", "按紧急程度就医", "再安排短时静心和通风清洁"),
            required_real_world_actions=("急重症及时联系当地急救", "遵从合格医疗人员建议"),
            contraindications=("delay_medical_care",),
            frequency_cap="静心每日不超过两次；净宅按正常清洁频率",
        ),
        _advice(
            "advice:fengshui:data-first",
            "fengshui",
            metaphysical_rationale="安宅、净宅与布局需以真实户型、用途和安全条件为前提。",
            real_world_problem="缺少户型、测量和居住信息时无法可靠判断空间方向。",
            recommended_action="资料不足，当前只建议安宅式清洁、通风、照明与动线整理，不提供坐向结论。",
            execution_steps=("排除消防与结构风险", "清理主要动线", "补齐户型和可靠测量后再复核"),
            required_real_world_actions=("遵守建筑与消防要求", "结构问题咨询专业人员"),
            required_inputs=("floor_plan", "reliable_measurement", "room_usage"),
        ),
        _advice(
            "advice:migration:readiness",
            "migration",
            metaphysical_rationale="迁移择时只作为办理阶段的文化提醒。",
            real_world_problem="迁移取决于签证、预算、语言、住房和工作安排。",
            recommended_action="先完成签证与预算核验；如需文化辅助，只把择时设为材料复核节点。",
            execution_steps=("查官方签证要求", "准备六个月预算", "核对语言与住房方案"),
            required_real_world_actions=("以官方移民信息为准", "保留应急返程方案"),
        ),
        _advice(
            "advice:art-and-skill:practice-ritual",
            "art_and_skill",
            metaphysical_rationale="开笔或开工仪式可作为长期练习的启动标记。",
            real_world_problem="技能成长取决于训练量、反馈质量和作品迭代。",
            recommended_action="可做一次低成本开笔或开工，并立即进入有反馈的练习计划。",
            execution_steps=("确定一个作品目标", "完成首次练习", "邀请可验证反馈", "按周期复盘"),
            required_real_world_actions=("记录练习时长", "保存版本对比", "接受专业反馈"),
        ),
    )
    return tuple(sorted(rules, key=lambda item: item.advice_id))


RuleType = TypeVar("RuleType", DomainRule, AdviceRule)


def production_rules(rules: Sequence[RuleType]) -> tuple[RuleType, ...]:
    selected: list[RuleType] = []
    for rule in rules:
        if rule.status not in RULE_LIFECYCLE_STATUSES:
            raise RuleGovernanceError(f"unknown rule status: {rule.status}")
        if rule.status == "production":
            selected.append(rule)
    return tuple(selected)


def _requested_wealth_repository(facts: Mapping[str, object]) -> bool:
    value = facts.get("ritual_interest")
    return value in {"wealth_repository", "补财库"}


def match_advice(
    domain: str,
    reality_facts: Mapping[str, object],
) -> tuple[AdviceRule, ...]:
    if domain not in RULE_DOMAINS:
        raise RuleGovernanceError(f"unknown advice domain: {domain}")
    if not isinstance(reality_facts, Mapping):
        raise RuleGovernanceError("reality_facts must be an object")
    catalog = production_rules(load_advice_rules())
    domain_rules = tuple(rule for rule in catalog if rule.domain == domain)

    if domain == "finance" and (
        reality_facts.get("cashflow_status") == "critical"
        or reality_facts.get("borrowing_for_ritual") is True
    ):
        return tuple(
            rule for rule in domain_rules if rule.advice_id == "advice:finance:ritual-decline"
        )

    selected: list[AdviceRule] = []
    for rule in domain_rules:
        if rule.advice_id == "advice:finance:ritual-decline":
            continue
        if rule.advice_id == "advice:finance:explicit-wealth-repository":
            if _requested_wealth_repository(reality_facts):
                selected.append(rule)
            continue
        selected.append(rule)
    if not selected:
        raise RuleGovernanceError(f"no production advice for domain: {domain}")
    return tuple(selected)


def validate_rule_catalogs() -> tuple[str, ...]:
    issues: list[str] = []
    domain_rules = load_domain_rules()
    advice_rules = load_advice_rules()
    if {rule.domain for rule in domain_rules} != set(RULE_DOMAINS):
        issues.append("domain_rule_coverage")
    if {rule.domain for rule in advice_rules} != set(RULE_DOMAINS):
        issues.append("advice_rule_coverage")

    seen: set[str] = set()
    for rule in (*domain_rules, *advice_rules):
        identifier = rule.rule_id if isinstance(rule, DomainRule) else rule.advice_id
        if identifier in seen:
            issues.append(f"duplicate_rule_id:{identifier}")
        seen.add(identifier)
        if rule.status not in RULE_LIFECYCLE_STATUSES:
            issues.append(f"unknown_status:{identifier}")
        if not rule.source_refs:
            issues.append(f"missing_source:{identifier}")
        if not rule.applicability:
            issues.append(f"missing_applicability:{identifier}")
        if not rule.counterexamples:
            issues.append(f"missing_counterexample:{identifier}")
        if not (
            rule.review.reviewer
            and rule.review.reviewed_at
            and rule.review.decision_id
        ):
            issues.append(f"missing_review:{identifier}")

    for rule in advice_rules:
        if rule.evidence_status != "traditional_culture_only":
            issues.append(f"invalid_evidence_status:{rule.advice_id}")
        if not rule.required_real_world_actions:
            issues.append(f"missing_real_world_action:{rule.advice_id}")
        if tuple(rule.prohibited_claims) != _PROHIBITED_CLAIMS:
            issues.append(f"prohibited_claim_contract:{rule.advice_id}")
        try:
            canonical_json(rule.to_dict())
        except (TypeError, ValueError):
            issues.append(f"non_canonical_rule:{rule.advice_id}")
    return tuple(issues)
