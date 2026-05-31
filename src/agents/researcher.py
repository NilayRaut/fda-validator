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



@weave.op
def researcher_node(state: dict) -> dict:
    drug, claim = state["drug"], state["claim"]
    if claim.get("stance") == "precedent_market":
        finding = _research_precedent_market(drug, claim)
    else:
        finding = _research_safety_efficacy(drug, claim)
    return {"findings": [finding]}   # append-only reducer merges parallel writes
