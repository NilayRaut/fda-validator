import weave
from ..llm import call_claude

# LANE: Synthesizer — owns synthesizer_node.
# Real impl (BUILD_SPEC §5): call_claude over the ledger → markdown report that PRESENTS
# the disagreement and flags low-confidence claims. Must NOT collapse contested findings
# into a single confident verdict (FR-6).

_SYSTEM = (
    "You are a regulatory analyst writing a briefing for a professional. You are given a "
    "disagreement ledger: per-topic positions, the critic's conflict verdict, and a COMPUTED "
    "confidence label. Write a concise markdown report that PRESERVES disagreement — surface "
    "where the evidence is contested, flag low/medium-confidence topics explicitly, and never "
    "collapse a contested topic into a single confident verdict. Do not invent facts beyond the "
    "ledger; state the computed confidence for each topic. End with what a professional should "
    "dig into next."
)


def _template_report(drug: str, ledger: list) -> str:
    # Deterministic fallback if the LLM call fails (fail-soft, BUILD_SPEC §8).
    lines = [f"# Regulatory analysis: {drug}", ""]
    for entry in ledger:
        lines.append(f"## {entry.get('topic', '')}")
        lines.append(f"- confidence: {entry.get('confidence')} ({entry.get('confidence_label')})")
        lines.append(f"- conflict: {entry.get('conflict', '')}")
        lines.append("")
    return "\n".join(lines)


@weave.op
def synthesizer_node(state: dict) -> dict:
    drug = state.get("drug", "")
    ledger = state.get("ledger", [])
    user = f"Drug: {drug}\n\nDisagreement ledger (JSON):\n{ledger}\n\nWrite the report."
    try:
        report = call_claude(_SYSTEM, user, use_search=False).get("text", "")
    except Exception:
        report = ""
    if not report.strip():
        report = _template_report(drug, ledger)
    return {"report": report}
