import json
import weave

from ..llm import call_claude

# LANE: Planner — owns planner_node.
# Real impl (BUILD_SPEC §5): call_claude (no search) → JSON array of exactly 2 claims,
# one per stance. Parse defensively (strip ```json fences, fall back to a 2-claim default).

STANCES = ("safety_efficacy", "precedent_market")

_SYSTEM = (
    "You are a regulatory research planner. Given a drug name and a user question, split the "
    "work into exactly two specialist research tracks and return ONLY a JSON array of two "
    'objects, each {"stance": <stance>, "question": <a focused research question for that track>}. '
    'The two stances are exactly "safety_efficacy" (clinical risk/benefit: adverse events, '
    'recalls, efficacy) and "precedent_market" (approval history and competitive market '
    "position). Output the JSON array only — no prose, no markdown fences."
)


def _fallback(drug: str) -> list[dict]:
    return [
        {"stance": "safety_efficacy",
         "question": f"What is the clinical risk/benefit profile of {drug}?"},
        {"stance": "precedent_market",
         "question": f"What is the approval history and market position of {drug}?"},
    ]


def _parse_claims(text: str, drug: str) -> list[dict]:
    # Extract the JSON array even if wrapped in prose or ```json fences.
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return _fallback(drug)
    try:
        data = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        return _fallback(drug)
    if not isinstance(data, list):
        return _fallback(drug)
    by_stance: dict[str, dict] = {}
    for item in data:
        if isinstance(item, dict) and item.get("stance") in STANCES and item.get("question"):
            by_stance[item["stance"]] = {"stance": item["stance"],
                                         "question": str(item["question"])}
    # Require exactly one claim per stance, else fall back to the safe default.
    if set(by_stance) != set(STANCES):
        return _fallback(drug)
    return [by_stance[s] for s in STANCES]


@weave.op
def planner_node(state: dict) -> dict:
    drug = state["drug"]
    question = state.get("question", "")
    try:  # fail soft (NFR-1): any API error → deterministic 2-claim default.
        out = call_claude(_SYSTEM, f"Drug: {drug}\nUser question: {question}", use_search=False)
        claims = _parse_claims(out.get("text", ""), drug)
    except Exception:
        claims = _fallback(drug)
    return {"claims": claims}
