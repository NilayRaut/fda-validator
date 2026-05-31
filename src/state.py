# FROZEN INTERFACE — these are the canonical data contracts (REQUIREMENTS.md §4).
# Every lane reads/writes these shapes. Do NOT change a field name/type without telling
# the whole team — it breaks other lanes. The `Annotated[list, add]` reducer on `findings`
# is MANDATORY: the two researchers write `findings` in parallel, and without the reducer
# LangGraph raises InvalidUpdateError on concurrent writes.
from typing import Annotated, TypedDict
from operator import add


class Finding(TypedDict):
    stance: str            # "safety_efficacy" | "precedent_market"
    claim: str
    conclusion: str
    evidence: list[dict]   # [{source, detail, url}]
    fda_data: dict         # raw openFDA payload used


class DisagreementEntry(TypedDict):
    topic: str
    positions: list[dict]  # [{stance, conclusion, evidence}]
    conflict: str
    confidence: float      # 0-1, COMPUTED (not LLM-generated)
    confidence_label: str  # "low" | "medium" | "high"


class ResearchState(TypedDict):
    drug: str
    question: str
    claims: list[dict]
    findings: Annotated[list[Finding], add]   # parallel writes — REDUCER, do not remove
    contradictions: list[dict]
    ledger: list[DisagreementEntry]
    report: str
