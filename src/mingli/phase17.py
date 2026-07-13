from __future__ import annotations

import json
from importlib.resources import files
from typing import Mapping, Sequence

from .contracts.serialization import digest
from .phase16 import _verify_phase16_result, build_phase16_fixture, evaluate_base_domain_contracts
from .phase17_contracts import (
    PHASE17_CALCULATION_VERSION, PHASE17_DECISION_ID, PHASE17_METHOD_ID, PHASE17_SCHEMA_VERSION,
    SCENARIOS, SCENARIO_LAYERS, Phase17InputError, ScenarioLayerAssessment, ScenarioRuleHit,
    SpecialScenarioAssessmentResult, record_digest,
)

DEFAULT_PHASE17_PROFILE_ID = "special-scenario-rules-r1@0.1"
RULE_RESOURCE = "phase17_special_scenario_rules_v0.1.json"
BLOCKED_OUTPUTS = {"guaranteed_admission", "guaranteed_reunion", "marriage_prediction", "natural_language_renderer"}


def load_phase17_rules() -> dict[str, object]:
    value = json.loads(files("mingli.derived.data").joinpath(RULE_RESOURCE).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Phase 17 rule manifest must be an object")
    return value


def get_phase17_profile(profile_id: str = DEFAULT_PHASE17_PROFILE_ID) -> dict[str, object]:
    result = dict(load_phase17_rules())
    if result.get("profile_id") != profile_id:
        raise ValueError(f"unsupported Phase 17 profile: {profile_id}")
    result["canonical_hash"] = digest({"record_type":"Phase17RuleProfile","payload":{k:v for k,v in result.items() if k != "canonical_hash"}})
    return result


def validate_phase17_rules() -> tuple[str, ...]:
    issues: list[str] = []
    try:
        profile = get_phase17_profile()
        if profile.get("decision_id") != PHASE17_DECISION_ID or profile.get("reviewed") is not True:
            issues.append("Phase 17 decision/review status is invalid")
        if profile.get("scenarios") != {key:list(value) for key,value in SCENARIO_LAYERS.items()}:
            issues.append("scenario layers must exactly match the contract")
        rules = profile.get("rules")
        if not isinstance(rules, list) or not rules:
            issues.append("rules must be non-empty")
            rules = []
        ids: set[str] = set()
        for rule in rules:
            if not isinstance(rule, Mapping):
                issues.append("rule must be an object"); continue
            rule_id = str(rule.get("rule_id", ""))
            if not rule_id or rule_id in ids: issues.append(f"duplicate rule_id: {rule_id}")
            ids.add(rule_id)
            scenario = str(rule.get("scenario"))
            if scenario not in SCENARIOS: issues.append(f"unsupported scenario: {scenario}"); continue
            if not set(rule.get("layers", ())) <= set(SCENARIO_LAYERS[scenario]): issues.append(f"invalid layers: {rule_id}")
            if rule.get("op") not in {"equals","in","gte","lte"}: issues.append(f"invalid op: {rule_id}")
            if rule.get("direction") not in {"support","conflict"}: issues.append(f"invalid direction: {rule_id}")
            if not isinstance(rule.get("priority"), int) or not 0 <= int(rule["priority"]) <= 100: issues.append(f"invalid priority: {rule_id}")
    except (ValueError, TypeError) as exc:
        issues.append(str(exc))
    return tuple(issues)


def phase17_schema_summary() -> dict[str, object]:
    return {"decision_id":PHASE17_DECISION_ID,"schema_version":PHASE17_SCHEMA_VERSION,"method_id":PHASE17_METHOD_ID,"calculation_version":PHASE17_CALCULATION_VERSION,"scenarios":{k:list(v) for k,v in SCENARIO_LAYERS.items()},"prediction_validity":"not_evaluated"}


def _matches(rule: Mapping[str, object], reality: Mapping[str, object]) -> bool:
    field = str(rule["field"])
    if field not in reality: return False
    found, expected, op = reality[field], rule.get("value"), rule["op"]
    if op == "equals": return found == expected
    if op == "in": return found in expected if isinstance(expected, list) else False
    if op in {"gte","lte"}:
        try: return float(found) >= float(expected) if op == "gte" else float(found) <= float(expected)
        except (TypeError, ValueError): return False
    return False


def _structural_label(label: str) -> str:
    return {"support_tendency":"support","conflict_tendency":"conflict","mixed_tendency":"conditional"}.get(label,"unresolved")


def evaluate_special_scenario(
    phase16_result: Mapping[str, object], *, scenario: str, target_id: str,
    reality_context: Mapping[str, object] | None = None, profile_id: str = DEFAULT_PHASE17_PROFILE_ID,
    requested_outputs: Sequence[str] = (),
) -> SpecialScenarioAssessmentResult:
    if scenario not in SCENARIOS: raise Phase17InputError(f"unsupported scenario: {scenario}")
    if set(requested_outputs) & BLOCKED_OUTPUTS: raise Phase17InputError("Phase 17 cannot return guaranteed admission, guaranteed reunion, marriage, or renderer outputs")
    payload16 = dict(phase16_result); _verify_phase16_result(payload16)
    source_domain = "career" if scenario == "career_exam" else "relationship"
    contracts = payload16.get("domain_contracts")
    if not isinstance(contracts, list): raise Phase17InputError("Phase 16 domain_contracts must be an array")
    source = next((item for item in contracts if isinstance(item, Mapping) and item.get("target_id") == target_id and item.get("domain") == source_domain), None)
    if source is None: raise Phase17InputError(f"missing Phase 16 {source_domain} contract for target: {target_id}")
    reality = dict(reality_context or {})
    reality_hash = digest({"record_type":"Phase17RealityInput","payload":reality})
    profile = get_phase17_profile(profile_id)
    raw_rules = profile["rules"]; assert isinstance(raw_rules, list)
    hits: list[ScenarioRuleHit] = []
    for rule in raw_rules:
        if not isinstance(rule, Mapping) or rule.get("scenario") != scenario or not _matches(rule, reality): continue
        for layer in rule["layers"]:
            hit_payload = {"hit_id":f"scenario-hit:{target_id}:{rule['rule_id']}:{layer}","rule_id":rule["rule_id"],"layer":layer,"direction":rule["direction"],"outcome_code":rule["outcome_code"],"priority":rule["priority"],"hard_override":rule["hard_override"],"source_field":rule["field"],"source_value":reality[rule["field"]]}
            hits.append(ScenarioRuleHit(**hit_payload, canonical_digest=record_digest("ScenarioRuleHit", hit_payload)))  # type: ignore[arg-type]
    layers: list[ScenarioLayerAssessment] = []; unresolved: list[dict[str, object]] = []
    structural_layer = "system_fit" if scenario == "career_exam" else "attraction"
    for layer in SCENARIO_LAYERS[scenario]:
        current = sorted((hit for hit in hits if hit.layer == layer), key=lambda item:(-item.priority,item.rule_id))
        hard = [hit for hit in current if hit.hard_override]
        reality_override = bool(hard)
        if hard:
            directions = {hit.direction for hit in hard if hit.priority == hard[0].priority}
            label = next(iter(directions)) if len(directions) == 1 else "unresolved"; confidence = "high" if len(directions) == 1 else "low"
        elif current:
            top_priority = current[0].priority; directions = {hit.direction for hit in current if hit.priority == top_priority}
            label = next(iter(directions)) if len(directions) == 1 else "conditional"; confidence = "high" if top_priority >= 90 and len(directions) == 1 else "medium"
        elif layer == structural_layer:
            label = _structural_label(str(source["judgement_label"])); confidence = str(source["confidence"])
        else:
            label = "unresolved"; confidence = "low"
        layer_payload = {"assessment_id":f"scenario-layer:{target_id}:{scenario}:{layer}","layer":layer,"label":label,"confidence":confidence,"outcome_codes":sorted({hit.outcome_code for hit in current}),"rule_hit_ids":[hit.hit_id for hit in current],"structural_source_contract_id":source["contract_id"] if layer == structural_layer else None,"reality_override":reality_override,"claim_boundary_codes":profile["claim_boundary_codes"]}
        layers.append(ScenarioLayerAssessment(**layer_payload, canonical_digest=record_digest("ScenarioLayerAssessment", layer_payload)))  # type: ignore[arg-type]
        if label in {"unresolved","conditional"}: unresolved.append({"code":"scenario_layer_not_resolved","layer":layer,"target_id":target_id})
    body = {"phase16_result_hash":payload16["canonical_hash"],"scenario":scenario,"target_id":target_id,"source_domain":source_domain,"reality_context_hash":reality_hash,"profile_id":profile_id,"rule_set_hash":profile["canonical_hash"],"rule_hits":[h.to_dict() for h in hits],"layers":[item.to_dict() for item in layers],"provenance_index":{"phase16_contract_id":source["contract_id"],"phase16_contract_digest":source["canonical_digest"],"reality_fields":sorted(reality)},"warnings":["special_scenario_layers_are_independent","reality_hard_override_is_layer_scoped","no_guaranteed_outcome","prediction_validity_not_evaluated"],"unresolved":unresolved}
    return SpecialScenarioAssessmentResult(
        phase16_result_hash=str(body["phase16_result_hash"]),
        scenario=scenario,  # type: ignore[arg-type]
        target_id=target_id,
        source_domain=source_domain,  # type: ignore[arg-type]
        reality_context_hash=reality_hash,
        profile_id=profile_id,
        rule_set_hash=str(profile["canonical_hash"]),
        rule_hits=tuple(hits),
        layers=tuple(layers),
        provenance_index=body["provenance_index"],  # type: ignore[arg-type]
        warnings=tuple(body["warnings"]),  # type: ignore[arg-type]
        unresolved=tuple(unresolved),
        canonical_hash=record_digest("SpecialScenarioAssessmentResult", body),
    )


def build_phase17_fixture() -> tuple[dict[str, object], str]:
    source = evaluate_base_domain_contracts(build_phase16_fixture("甲", "寅")).to_dict()
    return source, str(source["domain_contracts"][0]["target_id"])


def benchmark_phase17() -> dict[str, object]:
    failures = list(validate_phase17_rules()); total = passed = 0
    def check(ok: bool, message: str) -> None:
        nonlocal total, passed; total += 1
        if ok: passed += 1
        else: failures.append(message)
    source,target = build_phase17_fixture()
    cases = [
        ("career_exam",{"major_eligible":False,"preparation_months":1}),
        ("career_exam",{"major_eligible":True,"preparation_months":12,"mock_rank":"top_5_percent"}),
        ("relationship_reunion",{"contact_status":"no_contact","no_contact_months":24,"other_party_status":"married"}),
        ("relationship_reunion",{"contact_status":"active","both_willing":True,"breakup_reason":"distance"}),
        ("relationship_reunion",{"contact_status":"blocked","breakup_reason":"violence"}),
    ]
    for scenario,reality in cases:
        result=evaluate_special_scenario(source,scenario=scenario,target_id=target,reality_context=reality)
        expected=SCENARIO_LAYERS[scenario]
        checks=[tuple(item.layer for item in result.layers)==expected,len(result.layers)==4,result.prediction_validity=="not_evaluated",result.canonical_hash.startswith("sha256:"),all(item.canonical_digest.startswith("sha256:") for item in result.layers),result.canonical_hash==evaluate_special_scenario(json.loads(json.dumps(source,sort_keys=True)),scenario=scenario,target_id=target,reality_context=json.loads(json.dumps(reality,sort_keys=True))).canonical_hash]
        for index,ok in enumerate(checks,1): check(ok,f"{scenario} case check {index}")
    married=evaluate_special_scenario(source,scenario="relationship_reunion",target_id=target,reality_context={"other_party_status":"married"})
    check(next(x for x in married.layers if x.layer=="attraction").reality_override is False,"marriage leaked into attraction")
    check(all(next(x for x in married.layers if x.layer==layer).label=="conflict" for layer in ("recontact","reunion","stability")),"marriage hard boundary failed")
    ineligible=evaluate_special_scenario(source,scenario="career_exam",target_id=target,reality_context={"major_eligible":False})
    check(next(x for x in ineligible.layers if x.layer=="system_fit").reality_override is False,"eligibility leaked into fit")
    check(next(x for x in ineligible.layers if x.layer=="admission_outlook").label=="conflict","eligibility admission block failed")
    return {"assertions_total":total,"passed":passed,"failed":len(failures),"unresolved":0,"failures":failures}
