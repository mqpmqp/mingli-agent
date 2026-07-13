from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal, Mapping, Sequence

from .contracts.serialization import canonical_json, digest

PHASE18_SCHEMA_VERSION="evidence-fusion-orchestrator-result@0.1"
PHASE18_METHOD_ID="evidence-fusion-orchestrator@0.1.0"
PHASE18_CALCULATION_VERSION="0.1.0"
PHASE18_DECISION_ID="PHASE_18_UNIFIED_REALITY_EVIDENCE_FUSION_R1_APPROVED"
SOURCE_TYPES=("reality","chart","timing","rule","case")
ALIASES={"no_contact_duration_months":"no_contact_months","major_not_eligible":"major_eligible","product_or_customer_validation":"customer_validation","symptom":"symptoms"}
KNOWN_FIELDS=frozenset({"relationship_status","other_party_status","contact_status","no_contact_months","both_willing","breakup_reason","career_status","major_eligible","preparation_months","mock_rank","target_job_competition","capital_level","cash_runway_months","customer_validation","symptoms","contract_leverage","financial_risk","image_confirmed"})

class Phase18InputError(ValueError): pass

def _plain(value: object) -> dict[str, object]: return json.loads(canonical_json(asdict(value)))
def record_digest(kind: str,payload: Mapping[str,object])->str: return digest({"record_type":kind,"payload":{k:v for k,v in payload.items() if k not in {"canonical_digest","canonical_hash"}}})

@dataclass(frozen=True)
class UnifiedRealityContext:
    facts: Mapping[str,object]
    provided_fields: tuple[str,...]
    alias_resolutions: Mapping[str,str]
    warnings: tuple[str,...]
    canonical_hash: str
    schema_version: str=field(default="unified-reality-context@0.1",init=False)
    def to_dict(self)->dict[str,object]: return {"facts":dict(self.facts),"provided_fields":list(self.provided_fields),"alias_resolutions":dict(self.alias_resolutions),"warnings":list(self.warnings),"canonical_hash":self.canonical_hash,"schema_version":self.schema_version}

@dataclass(frozen=True)
class FusionEvidence:
    evidence_id: str; claim_id: str; scope: str; source_type: str; source_id: str
    direction: Literal["support","contradict"]; weight: str; priority: int; verified: bool; detail_code: str; canonical_digest: str
    def to_dict(self)->dict[str,object]: return _plain(self)

@dataclass(frozen=True)
class FusedClaim:
    claim_id: str; scope: str; status: str; support_score: str; contradict_score: str
    hard_override_direction: Literal["support","contradict"]|None; evidence_ids: tuple[str,...]
    winning_evidence_ids: tuple[str,...]; conflicting_evidence_ids: tuple[str,...]; confidence: Literal["high","medium","low"]; canonical_digest: str
    def to_dict(self)->dict[str,object]: return _plain(self)

@dataclass(frozen=True)
class EvidenceFusionOrchestratorResult:
    reality_context_hash: str; evidence: tuple[FusionEvidence,...]; claims: tuple[FusedClaim,...]
    provenance_index: Mapping[str,object]; warnings: tuple[str,...]; unresolved: tuple[Mapping[str,object],...]; canonical_hash: str
    schema_version: str=field(default=PHASE18_SCHEMA_VERSION,init=False); method_id: str=field(default=PHASE18_METHOD_ID,init=False); calculation_version: str=field(default=PHASE18_CALCULATION_VERSION,init=False); prediction_validity: Literal["not_evaluated"]=field(default="not_evaluated",init=False)
    def to_dict(self)->dict[str,object]: return {"reality_context_hash":self.reality_context_hash,"evidence":[x.to_dict() for x in self.evidence],"claims":[x.to_dict() for x in self.claims],"provenance_index":dict(self.provenance_index),"warnings":list(self.warnings),"unresolved":list(self.unresolved),"canonical_hash":self.canonical_hash,"schema_version":self.schema_version,"method_id":self.method_id,"calculation_version":self.calculation_version,"prediction_validity":self.prediction_validity}

def normalize_reality_context(raw: Mapping[str,object]) -> UnifiedRealityContext:
    if not isinstance(raw,Mapping): raise Phase18InputError("reality context must be an object")
    facts: dict[str,object]={}; aliases: dict[str,str]={}; warnings: list[str]=[]
    for key,value in raw.items():
        canonical=ALIASES.get(key,key)
        if canonical not in KNOWN_FIELDS: raise Phase18InputError(f"unknown reality field: {key}")
        if key=="major_not_eligible": value=not bool(value)
        if canonical in facts and facts[canonical]!=value: raise Phase18InputError(f"conflicting reality aliases: {canonical}")
        facts[canonical]=value
        if canonical!=key: aliases[key]=canonical
    for numeric in ("no_contact_months","preparation_months","cash_runway_months"):
        if numeric in facts and (isinstance(facts[numeric],bool) or not isinstance(facts[numeric],(int,float)) or float(facts[numeric])<0): raise Phase18InputError(f"{numeric} must be a non-negative number")
    body={"facts":{k:facts[k] for k in sorted(facts)},"provided_fields":sorted(raw),"alias_resolutions":aliases,"warnings":warnings}
    return UnifiedRealityContext(facts=body["facts"],provided_fields=tuple(body["provided_fields"]),alias_resolutions=aliases,warnings=tuple(warnings),canonical_hash=record_digest("UnifiedRealityContext",body))

def _parse_evidence(items: Sequence[Mapping[str,object]]) -> tuple[FusionEvidence,...]:
    records=[]; seen=set()
    for index,item in enumerate(items,1):
        evidence_id=str(item.get("evidence_id") or f"fusion-evidence:{index}")
        if evidence_id in seen: raise Phase18InputError(f"duplicate evidence_id: {evidence_id}")
        seen.add(evidence_id); source_type=str(item.get("source_type")); direction=str(item.get("direction"))
        if source_type not in SOURCE_TYPES: raise Phase18InputError(f"unsupported source_type: {source_type}")
        if direction not in {"support","contradict"}: raise Phase18InputError("direction must be support or contradict")
        try: weight=float(item.get("weight",0))
        except (TypeError,ValueError) as exc: raise Phase18InputError("weight must be numeric") from exc
        priority=item.get("priority",50)
        if not 0<=weight<=10 or isinstance(priority,bool) or not isinstance(priority,int) or not 0<=priority<=100: raise Phase18InputError("weight/priority out of range")
        payload={"evidence_id":evidence_id,"claim_id":str(item.get("claim_id","")),"scope":str(item.get("scope","global")),"source_type":source_type,"source_id":str(item.get("source_id","")),"direction":direction,"weight":format(weight,".4f"),"priority":priority,"verified":item.get("verified") is True,"detail_code":str(item.get("detail_code","unspecified"))}
        if not payload["claim_id"] or not payload["source_id"]: raise Phase18InputError("claim_id and source_id are required")
        records.append(FusionEvidence(**payload,canonical_digest=record_digest("FusionEvidence",payload)))  # type: ignore[arg-type]
    return tuple(sorted(records,key=lambda x:x.evidence_id))

def orchestrate_evidence_fusion(reality: UnifiedRealityContext|Mapping[str,object], evidence_items: Sequence[Mapping[str,object]]) -> EvidenceFusionOrchestratorResult:
    context=reality if isinstance(reality,UnifiedRealityContext) else normalize_reality_context(reality)
    evidence=_parse_evidence(evidence_items); claims=[]; unresolved=[]
    groups=sorted({(x.claim_id,x.scope) for x in evidence})
    for claim_id,scope in groups:
        group=[x for x in evidence if x.claim_id==claim_id and x.scope==scope]
        verified_reality=[x for x in group if x.source_type=="reality" and x.verified]
        reality_dirs={x.direction for x in verified_reality}
        hard=next(iter(reality_dirs)) if len(reality_dirs)==1 else None
        support=sum(float(x.weight) for x in group if x.direction=="support"); contradict=sum(float(x.weight) for x in group if x.direction=="contradict")
        winning=[]; conflicting=[]
        if len(reality_dirs)>1: status="unresolved_conflict"; confidence="low"; conflicting=[x.evidence_id for x in verified_reality]; hard=None
        elif hard:
            status="resolved_by_reality_override"; confidence="high"; winning=[x.evidence_id for x in verified_reality]; conflicting=[x.evidence_id for x in group if x.direction!=hard]
        else:
            top=max((x.priority for x in group),default=0); leaders=[x for x in group if x.priority==top]; dirs={x.direction for x in leaders}
            if len(dirs)>1: status="unresolved_conflict"; confidence="low"; conflicting=[x.evidence_id for x in leaders]
            elif leaders: status="resolved_by_priority"; confidence="medium"; winning=[x.evidence_id for x in leaders]; conflicting=[x.evidence_id for x in group if x.direction!=leaders[0].direction]
            else: status="no_evidence"; confidence="low"
        if status=="unresolved_conflict": unresolved.append({"claim_id":claim_id,"scope":scope,"code":"evidence_conflict_unresolved"})
        payload={"claim_id":claim_id,"scope":scope,"status":status,"support_score":format(support,".4f"),"contradict_score":format(contradict,".4f"),"hard_override_direction":hard,"evidence_ids":[x.evidence_id for x in group],"winning_evidence_ids":sorted(winning),"conflicting_evidence_ids":sorted(conflicting),"confidence":confidence}
        claims.append(FusedClaim(**payload,canonical_digest=record_digest("FusedClaim",payload)))  # type: ignore[arg-type]
    body={"reality_context_hash":context.canonical_hash,"evidence":[x.to_dict() for x in evidence],"claims":[x.to_dict() for x in claims],"provenance_index":{"reality_fields":list(context.facts),"evidence_sources":sorted({x.source_id for x in evidence})},"warnings":["reality_override_is_claim_and_scope_specific","contradictory_evidence_is_preserved","prediction_validity_not_evaluated"],"unresolved":unresolved}
    return EvidenceFusionOrchestratorResult(reality_context_hash=context.canonical_hash,evidence=evidence,claims=tuple(claims),provenance_index=body["provenance_index"],warnings=tuple(body["warnings"]),unresolved=tuple(unresolved),canonical_hash=record_digest("EvidenceFusionOrchestratorResult",body))  # type: ignore[arg-type]

def benchmark_phase18()->dict[str,object]:
    total=passed=0; failures=[]
    def check(ok,msg):
        nonlocal total,passed; total+=1
        if ok: passed+=1
        else: failures.append(msg)
    context=normalize_reality_context({"no_contact_duration_months":24,"major_not_eligible":True})
    check(context.facts["no_contact_months"]==24,"alias failed"); check(context.facts["major_eligible"] is False,"inverse alias failed")
    items=[{"evidence_id":"chart","claim_id":"reunion","scope":"t1:reunion","source_type":"chart","source_id":"p16","direction":"support","weight":10,"priority":80,"verified":False},{"evidence_id":"reality","claim_id":"reunion","scope":"t1:reunion","source_type":"reality","source_id":"user","direction":"contradict","weight":0,"priority":100,"verified":True}]
    result=orchestrate_evidence_fusion(context,items); claim=result.claims[0]
    for ok,msg in [(claim.status=="resolved_by_reality_override","override status"),(claim.hard_override_direction=="contradict","override direction"),("chart" in claim.conflicting_evidence_ids,"conflict preservation"),(result.prediction_validity=="not_evaluated","prediction boundary"),(result.canonical_hash==orchestrate_evidence_fusion(context,json.loads(json.dumps(items,sort_keys=True))).canonical_hash,"determinism")]: check(ok,msg)
    conflict=orchestrate_evidence_fusion({},[{**items[1],"evidence_id":"r1","direction":"support"},{**items[1],"evidence_id":"r2","direction":"contradict"}]).claims[0]
    check(conflict.status=="unresolved_conflict","reality conflict"); check(conflict.hard_override_direction is None,"conflicting hard override")
    return {"assertions_total":total,"passed":passed,"failed":len(failures),"unresolved":0,"failures":failures}
