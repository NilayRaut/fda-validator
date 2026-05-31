import weave


def _has_fda_records(fda_data: dict) -> bool:
    # True only if a fetcher actually returned records. Guards against crediting "grounding"
    # for an EMPTY openFDA payload (e.g. investigational drugs absent from these databases),
    # which would otherwise hand out false confidence on no data.
    for value in (fda_data or {}).values():
        if isinstance(value, dict):
            for inner in value.values():
                if isinstance(inner, list) and inner:
                    return True
    return False


@weave.op
def compute_confidence(finding: dict, contradiction: dict) -> tuple[float, str]:
    # COMPUTED from observable signals — reproducible and explainable. Do NOT ask the LLM
    # for a confidence number (FR-5 / NFR-3).
    score = 0.5
    score += min(len(finding.get("evidence", [])), 4) * 0.08
    fda_data = finding.get("fda_data", {})
    if str(fda_data.get("source", "")).startswith("openFDA") and _has_fda_records(fda_data):
        score += 0.15
    verdict = (contradiction or {}).get("verdict", "silent")
    if verdict == "contradicts": score -= 0.35
    elif verdict == "supports":  score += 0.15
    score = max(0.0, min(1.0, score))
    return round(score, 2), ("high" if score >= 0.7 else "medium" if score >= 0.4 else "low")
