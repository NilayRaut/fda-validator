import weave

# LANE: Planner — owns planner_node.
# Real impl (BUILD_SPEC §5): call_claude (no search) → JSON array of exactly 2 claims,
# one per stance. Parse defensively (strip ```json fences, fall back to a 2-claim default).


@weave.op
def planner_node(state: dict) -> dict:
    drug = state["drug"]
    # TODO(planner): replace with call_claude + defensive JSON parse.
    claims = [
        {"stance": "safety_efficacy",
         "question": f"What is the clinical risk/benefit profile of {drug}?"},
        {"stance": "precedent_market",
         "question": f"What is the approval history and market position of {drug}?"},
    ]
    return {"claims": claims}
