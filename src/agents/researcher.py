import weave
from ..llm import call_claude
from ..openfda import adverse_events, recalls, approvals, marketed_products
from ..ctgov import clinical_trials

# Each researcher grounds its finding in LIVE data: openFDA (marketed products) + ClinicalTrials.gov
# (investigational compounds absent from openFDA). If neither returns records, a deterministic
# disclaimer marks the finding as NOT grounded so the LLM can't pass off parametric memory as evidence.

_NO_DATA_NOTE = (
    "_⚠️ No openFDA or ClinicalTrials.gov records were found for this drug name (check the spelling, or "
    "it may be an internal code not indexed). The assessment below is general background — NOT grounded "
    "in retrieved data — and should be independently verified._\n\n"
)


def _has_records(*payloads) -> bool:
    # True only if a fetcher returned actual records (top_reactions/recalls/applications/products/trials).
    for p in payloads:
        for v in (p or {}).values():
            if isinstance(v, list) and v:
                return True
    return False


def _build_evidence(fda_payload: dict, claude_result: dict) -> list[dict]:
    evidence = [{"source": fda_payload.get("source", "openFDA"), "detail": str(fda_payload), "url": ""}]
    for c in claude_result.get("citations", []):
        evidence.append({
            "source": c.get("source", "web"),
            "detail": c.get("detail", ""),
            "url": c.get("url", ""),
        })
    return evidence


def _trial_evidence(cts: dict) -> list[dict]:
    return [{"source": "ClinicalTrials.gov",
             "detail": f"{t.get('nct_id')} [{t.get('phase') or 'phase n/a'} · {t.get('status')}] "
                       f"{t.get('title')} — {t.get('sponsor')} ({t.get('conditions')})",
             "url": t.get("url", "")} for t in cts.get("trials", [])]


@weave.op
def _research_safety_efficacy(drug: str, claim: dict) -> dict:
    ae = adverse_events(drug)
    rec = recalls(drug)
    cts = clinical_trials(drug)

    question = claim.get("question", f"What are the safety and efficacy characteristics of {drug}?")
    evidence_summary = (
        f"openFDA FAERS top adverse reactions: {ae.get('top_reactions', [])}\n"
        f"openFDA recalls: {rec.get('recalls', [])}\n"
        f"ClinicalTrials.gov studies: {cts.get('trials', [])}\n"
        f"(fetch errors: FAERS={ae.get('_error', '')}; recalls={rec.get('_error', '')}; "
        f"ctgov={cts.get('_error', '')})"
    )
    system = (
        "You are an FDA regulatory researcher specializing in drug safety and efficacy. Use ONLY the "
        "provided evidence (openFDA FAERS/recalls and ClinicalTrials.gov studies) to write a concise "
        "conclusion about the drug's safety profile, adverse events, and clinical/trial evidence. For "
        "investigational drugs there may be no openFDA data but active trials — reason from those and "
        "name their phase/status. Do not cite outside literature not included here. State limitations plainly."
    )
    user = (
        f"Drug: {drug}\nResearch question: {question}\n\n"
        f"Evidence:\n{evidence_summary}\n\n"
        "Write a 2-3 sentence conclusion grounded only in the provided evidence."
    )
    try:  # fail-soft (BUILD_SPEC §8): a degraded finding beats a graph that throws
        result = call_claude(system, user, use_search=False)
    except Exception as e:
        result = {"text": f"[safety_efficacy LLM unavailable: {e}]", "citations": []}

    src = []
    if _has_records(ae, rec): src.append("openFDA FAERS/enforcement")
    if _has_records(cts): src.append("ClinicalTrials.gov")
    fda_data = {"adverse_events": ae, "recalls": rec, "clinical_trials": cts,
                "source": " + ".join(src) if src else "no records found"}
    conclusion = result["text"]
    if not _has_records(ae, rec, cts):  # deterministic honesty guard for no-data drugs
        conclusion = _NO_DATA_NOTE + conclusion
    return {
        "stance": "safety_efficacy",
        "claim": question,
        "conclusion": conclusion,
        "evidence": _build_evidence(fda_data, result) + _trial_evidence(cts),
        "fda_data": fda_data,
    }


@weave.op
def _research_precedent_market(drug: str, claim: dict) -> dict:
    apps = approvals(drug)
    mkt = marketed_products(drug)
    cts = clinical_trials(drug)

    question = claim.get("question", f"What is the regulatory precedent and market landscape for {drug}?")
    evidence_summary = (
        f"openFDA Drugs@FDA applications: {apps.get('applications', [])}\n"
        f"openFDA NDC marketed products: {mkt.get('products', [])}\n"
        f"ClinicalTrials.gov studies (development stage): {cts.get('trials', [])}\n"
        f"(fetch errors: approvals={apps.get('_error', '')}; ndc={mkt.get('_error', '')}; "
        f"ctgov={cts.get('_error', '')})"
    )
    system = (
        "You are an FDA regulatory researcher specializing in drug approval history and market competition. "
        "Use ONLY the provided evidence (openFDA Drugs@FDA/NDC and ClinicalTrials.gov) to write a concise "
        "conclusion about the drug's regulatory precedent, market presence, and competitive landscape. For "
        "investigational drugs with no approvals, characterize the development stage from trial phase/sponsor. "
        "Do not cite outside literature not included here. State limitations plainly."
    )
    user = (
        f"Drug: {drug}\nResearch question: {question}\n\n"
        f"Evidence:\n{evidence_summary}\n\n"
        "Write a 2-3 sentence conclusion grounded only in the provided evidence."
    )
    try:  # fail-soft (BUILD_SPEC §8): a degraded finding beats a graph that throws
        result = call_claude(system, user, use_search=False)
    except Exception as e:
        result = {"text": f"[precedent_market LLM unavailable: {e}]", "citations": []}

    src = []
    if _has_records(apps, mkt): src.append("openFDA Drugs@FDA/NDC")
    if _has_records(cts): src.append("ClinicalTrials.gov")
    fda_data = {"approvals": apps, "marketed_products": mkt, "clinical_trials": cts,
                "source": " + ".join(src) if src else "no records found"}
    conclusion = result["text"]
    if not _has_records(apps, mkt, cts):  # deterministic honesty guard for no-data drugs
        conclusion = _NO_DATA_NOTE + conclusion
    return {
        "stance": "precedent_market",
        "claim": question,
        "conclusion": conclusion,
        "evidence": _build_evidence(fda_data, result) + _trial_evidence(cts),
        "fda_data": fda_data,
    }


@weave.op
def researcher_node(state: dict) -> dict:
    drug, claim = state["drug"], state["claim"]
    if claim.get("stance") == "precedent_market":
        finding = _research_precedent_market(drug, claim)
    else:
        finding = _research_safety_efficacy(drug, claim)
    return {"findings": [finding]}
