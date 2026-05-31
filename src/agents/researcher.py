import weave
from ..llm import call_claude
from ..openfda import adverse_events, recalls, approvals, marketed_products


def _build_evidence(fda_payload: dict, claude_result: dict) -> list[dict]:
    evidence = [{"source": fda_payload.get("source", "openFDA"), "detail": str(fda_payload), "url": ""}]
    for c in claude_result.get("citations", []):
        evidence.append({
            "source": c.get("source", "web"),
            "detail": c.get("detail", ""),
            "url": c.get("url", ""),
        })
    return evidence


@weave.op
def _research_safety_efficacy(drug: str, claim: dict) -> dict:
    ae = adverse_events(drug)
    rec = recalls(drug)

    question = claim.get("question", f"What are the safety and efficacy characteristics of {drug}?")
    fda_summary = (
        f"Top adverse reactions: {ae.get('top_reactions', [])}\n"
        f"Adverse-event fetch error: {ae.get('_error', '')}\n"
        f"Recalls: {rec.get('recalls', [])}\n"
        f"Recall fetch error: {rec.get('_error', '')}"
    )
    system = (
        "You are an FDA regulatory researcher specializing in drug safety and efficacy. "
        "Use only the provided openFDA data to write a concise conclusion about "
        "the drug's safety profile, known adverse events, and clinical efficacy evidence. "
        "Do not cite or rely on outside literature unless it is included in the input. "
        "If the provided data is limited or an openFDA fetch failed, state that limitation."
    )
    user = (
        f"Drug: {drug}\nResearch question: {question}\n\n"
        f"openFDA data:\n{fda_summary}\n\n"
        "Write a 2-3 sentence conclusion grounded only in the provided openFDA data."
    )
    try:  # fail-soft (BUILD_SPEC §8): a degraded finding beats a graph that throws
        result = call_claude(system, user, use_search=False)
    except Exception as e:
        result = {"text": f"[safety_efficacy LLM unavailable: {e}]", "citations": []}

    fda_data = {"adverse_events": ae, "recalls": rec, "source": ae.get("source", "openFDA")}
    return {
        "stance": "safety_efficacy",
        "claim": question,
        "conclusion": result["text"],
        "evidence": _build_evidence(fda_data, result),
        "fda_data": fda_data,
    }


@weave.op
def _research_precedent_market(drug: str, claim: dict) -> dict:
    apps = approvals(drug)
    mkt = marketed_products(drug)

    question = claim.get("question", f"What is the regulatory precedent and market landscape for {drug}?")
    fda_summary = (
        f"FDA applications: {apps.get('applications', [])}\n"
        f"Approval fetch error: {apps.get('_error', '')}\n"
        f"Marketed products: {mkt.get('products', [])}\n"
        f"Marketed-products fetch error: {mkt.get('_error', '')}"
    )
    system = (
        "You are an FDA regulatory researcher specializing in drug approval history and market competition. "
        "Use only the provided openFDA data to write a concise conclusion about "
        "the drug's regulatory approval precedent, current market presence, and competitive landscape. "
        "Do not cite or rely on outside literature unless it is included in the input. "
        "If the provided data is limited or an openFDA fetch failed, state that limitation."
    )
    user = (
        f"Drug: {drug}\nResearch question: {question}\n\n"
        f"openFDA data:\n{fda_summary}\n\n"
        "Write a 2-3 sentence conclusion grounded only in the provided openFDA data."
    )
    try:  # fail-soft (BUILD_SPEC §8): a degraded finding beats a graph that throws
        result = call_claude(system, user, use_search=False)
    except Exception as e:
        result = {"text": f"[precedent_market LLM unavailable: {e}]", "citations": []}

    fda_data = {"approvals": apps, "marketed_products": mkt, "source": apps.get("source", "openFDA")}
    return {
        "stance": "precedent_market",
        "claim": question,
        "conclusion": result["text"],
        "evidence": _build_evidence(fda_data, result),
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
