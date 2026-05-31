import weave
from .confidence import compute_confidence

# LANE: Disagreement + Confidence — owns disagreement.py (and tunes confidence.py).
# Wired to the REAL compute_confidence even in the scaffold so the deterministic path is
# exercised end-to-end from day one. Matches each finding to the critic's contradiction by
# stance, computes confidence, and assembles one DisagreementEntry per claim.


@weave.op
def disagreement_node(state: dict) -> dict:
    findings = state.get("findings", [])
    contradictions = state.get("contradictions", [])
    by_stance = {c.get("stance"): c for c in contradictions}

    ledger = []
    for f in findings:
        contradiction = by_stance.get(f.get("stance"), {})
        confidence, label = compute_confidence(f, contradiction)
        ledger.append({
            "topic": f.get("claim", ""),
            "positions": [{"stance": f.get("stance"), "conclusion": f.get("conclusion"),
                           "evidence": f.get("evidence", [])}],
            "conflict": contradiction.get("verdict", "silent"),
            "confidence": confidence,
            "confidence_label": label,
        })
    return {"ledger": ledger}
