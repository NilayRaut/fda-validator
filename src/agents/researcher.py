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
    fda_summary = f"Top adverse reactions: {ae.get('top_reactions', [])}\nRecalls: {rec.get('recalls', [])}"
    system = (
        "You are an FDA regulatory researcher specializing in drug safety and efficacy. "
        "Use the provided openFDA data AND web search to write a concise conclusion about "
        "the drug's safety profile, known adverse events, and clinical efficacy evidence. "
        "Cite your sources."
    )
    user = (
        f"Drug: {drug}\nResearch question: {question}\n\n"
        f"openFDA data:\n{fda_summary}\n\n"
        "Write a 2-3 sentence conclusion grounded in this data and current literature."
    )
    try:  # fail-soft (BUILD_SPEC §8): a degraded finding beats a graph that throws
        result = call_claude(system, user, use_search=True, max_uses=3)
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
    fda_summary = f"FDA applications: {apps.get('applications', [])}\nMarketed products: {mkt.get('products', [])}"
    system = (
        "You are an FDA regulatory researcher specializing in drug approval history and market competition. "
        "Use the provided openFDA data AND web search to write a concise conclusion about "
        "the drug's regulatory approval precedent, current market presence, and competitive landscape. "
        "Cite your sources."
    )
    user = (
        f"Drug: {drug}\nResearch question: {question}\n\n"
        f"openFDA data:\n{fda_summary}\n\n"
        "Write a 2-3 sentence conclusion grounded in this data and current literature."
    )
    try:  # fail-soft (BUILD_SPEC §8): a degraded finding beats a graph that throws
        result = call_claude(system, user, use_search=True, max_uses=3)
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
