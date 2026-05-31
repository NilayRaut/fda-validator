import weave


@weave.op
def compute_confidence(finding: dict, contradiction: dict) -> tuple[float, str]:
    # COMPUTED from observable signals — reproducible and explainable. Do NOT ask the LLM
    # for a confidence number (FR-5 / NFR-3).
    score = 0.5
    score += min(len(finding.get("evidence", [])), 4) * 0.08
    if str(finding.get("fda_data", {}).get("source", "")).startswith("openFDA"):
        score += 0.15
    verdict = (contradiction or {}).get("verdict", "silent")
    if verdict == "contradicts": score -= 0.35
    elif verdict == "supports":  score += 0.15
    score = max(0.0, min(1.0, score))
    return round(score, 2), ("high" if score >= 0.7 else "medium" if score >= 0.4 else "low")
