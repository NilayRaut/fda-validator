import weave

# LANE: Synthesizer — owns synthesizer_node.
# Real impl (BUILD_SPEC §5): call_claude over the ledger → markdown report that PRESENTS
# the disagreement and flags low-confidence claims. Must NOT collapse contested findings
# into a single confident verdict (FR-6).


@weave.op
def synthesizer_node(state: dict) -> dict:
    ledger = state.get("ledger", [])
    # TODO(synthesizer): replace template with call_claude that surfaces conflict.
    lines = [f"# Regulatory analysis: {state.get('drug', '')}", "", "_[stub report]_", ""]
    for entry in ledger:
        lines.append(f"## {entry.get('topic', '')}")
        lines.append(f"- confidence: {entry.get('confidence')} ({entry.get('confidence_label')})")
        lines.append(f"- conflict: {entry.get('conflict', '')}")
        lines.append("")
    return {"report": "\n".join(lines)}
