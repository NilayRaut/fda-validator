import weave
from ..openfda import approvals, marketed_products
from ..llm import call_claude

# This node is a TWO-PERSON lane. researcher_node branches on the claim's stance and
# delegates to one helper per track, so the two owners each edit their OWN function:
#   - Safety & Efficacy lane → _research_safety_efficacy
#   - Precedent & Market lane → _research_precedent_market
# Real impl (BUILD_SPEC §5): each helper calls its openFDA fetcher(s) (+ web search via
# call_claude) and returns one Finding matching the frozen shape in src/state.py.


def _research_safety_efficacy(drug: str, claim: dict) -> dict:
    # TODO(safety_efficacy): adverse_events(drug) + recalls(drug) + call_claude for efficacy.
    return {
        "stance": "safety_efficacy",
        "claim": claim.get("question", ""),
        "conclusion": f"[stub] safety & efficacy conclusion for {drug}",
        "evidence": [{"source": "stub", "detail": "placeholder", "url": ""}],
        "fda_data": {"source": "stub"},
    }


def _research_precedent_market(drug: str, claim: dict) -> dict:
    question = claim.get("question", "")
    # Deterministic openFDA pulls: approval history (Drugs@FDA) + marketed products (NDC).
    appr = approvals(drug)
    mkt = marketed_products(drug)

    # Characterizes system
    system = ("You are a pharmaceutical regulatory-affairs analyst. Ground every claim in the "
              "openFDA data provided; use web search ONLY to characterize the competitive "
              "landscape (rival brands, generics, market position). Be concise and state plainly "
              "what the FDA data does and does not show.")
    # User prompt
    user = (f"Question: {question}\n\n"
            f"Drugs@FDA approval history (openFDA): {appr}\n\n"
            f"NDC marketed products (openFDA): {mkt}\n\n"
            "Summarize the approval history and application type, then the competitive landscape.")
    try:  # fail-soft: a degraded finding beats a graph that throws (BUILD_SPEC §8)
        llm = call_claude(system, user, use_search=True, max_uses=3)
    except Exception as e:
        llm = {"text": f"[precedent_market LLM unavailable: {e}]", "citations": []}

    # Evidence = FDA-derived facts + web-search citations, all in the frozen {source, detail, url} shape.
    evidence = [
        {"source": appr.get("source", "openFDA Drugs@FDA"),
         "detail": f"App {a.get('application_number')} — {a.get('sponsor')} — {a.get('products')}",
         "url": "https://www.accessdata.fda.gov/scripts/cder/daf/"}
        for a in appr.get("applications", [])
    ] + [
        {"source": mkt.get("source", "openFDA NDC"),
         "detail": f"{p.get('brand')} — {p.get('manufacturer')} ({p.get('class')})", "url": ""}
        for p in mkt.get("products", [])
    ] + llm.get("citations", [])

    return {
        "stance": "precedent_market",
        "claim": question,
        "conclusion": llm.get("text", ""),
        "evidence": evidence,
        # source MUST start with "openFDA" so compute_confidence credits the grounding (confidence.py).
        "fda_data": {"source": "openFDA Drugs@FDA + NDC", "approvals": appr, "marketed_products": mkt},
    } 


@weave.op
def researcher_node(state: dict) -> dict:
    drug, claim = state["drug"], state["claim"]
    if claim.get("stance") == "precedent_market":
        finding = _research_precedent_market(drug, claim)
    else:
        finding = _research_safety_efficacy(drug, claim)
    return {"findings": [finding]}   # append-only reducer merges parallel writes
