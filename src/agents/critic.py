import weave

# LANE: Critic — owns critic_node.
# THE principle that must not break: the critic searches INDEPENDENTLY. It must NOT read a
# finding's evidence/fda_data. For each finding it runs its own openFDA queries
# (adverse_events/recalls for safety; approvals for precedent) AND adversarial call_claude
# queries ("limitations of <claim>", "<drug> safety concerns", "<drug> contradicting evidence"),
# then emits a verdict in {supports, contradicts, silent} with its OWN sources.


@weave.op
def critic_node(state: dict) -> dict:
    findings = state.get("findings", [])
    # TODO(critic): independent openFDA + adversarial call_claude per finding.
    contradictions = [
        {
            "stance": f.get("stance", ""),
            "claim": f.get("claim", ""),
            "verdict": "silent",   # {supports, contradicts, silent}
            "evidence": [],
        }
        for f in findings
    ]
    return {"contradictions": contradictions}
