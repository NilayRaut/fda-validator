import re

import weave
from ..openfda import adverse_events, approvals, recalls

# LANE: Critic — owns critic_node.
# THE principle that must not break: the critic searches INDEPENDENTLY. It must NOT read a
# finding's evidence/fda_data. For each finding it runs its own openFDA queries
# (adverse_events/recalls for safety; approvals for precedent), then emits a verdict in
# {supports, contradicts, silent} with its OWN sources. This openFDA-only implementation
# intentionally does not import src/llm.py so keyless clones still run.

FAERS_URL = "https://open.fda.gov/apis/drug/event/"
ENFORCEMENT_URL = "https://open.fda.gov/apis/drug/enforcement/"
DRUGSFDA_URL = "https://open.fda.gov/apis/drug/drugsfda/"

SAFETY_OPTIMISTIC_TERMS = (
    "safe", "safety profile", "manageable", "low risk", "well tolerated",
    "favorable", "no major", "no significant", "acceptable", "benign",
)
SAFETY_RISK_TERMS = (
    "adverse", "reaction", "event", "risk", "warning", "recall", "concern",
    "safety signal",
)
PRECEDENT_TERMS = (
    "approved", "approval", "precedent", "regulatory history", "marketed",
    "application", "nda", "anda", "bla", "drugs@fda",
)
NO_PRECEDENT_TERMS = (
    "not approved", "no approval", "no precedent", "lacks approval",
    "without approval", "no regulatory precedent",
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    for term in terms:
        pattern = r"(?<![a-z0-9_])" + re.escape(term.lower()) + r"(?![a-z0-9_])"
        if re.search(pattern, lower):
            return True
    return False


def _compact(value: object, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _format_reaction(item: dict) -> str:
    term = item.get("term") or item.get("reactionmeddrapt") or "unknown reaction"
    count = item.get("count")
    if count is None:
        return str(term)
    return f"{term} ({count} reports)"


@weave.op
def _critic_safety_efficacy(drug: str) -> list[dict]:
    """Gather independent openFDA safety evidence without reading researcher sources."""
    evidence = []

    events = adverse_events(drug)
    top_reactions = events.get("top_reactions", []) if isinstance(events, dict) else []
    if top_reactions:
        reactions = ", ".join(_format_reaction(item) for item in top_reactions[:5])
        evidence.append({
            "source": "openFDA FAERS (drug/event)",
            "detail": f"Top reported adverse reactions for {drug}: {reactions}. FAERS is signal data, not proof of causality.",
            "url": FAERS_URL,
        })

    enforcement = recalls(drug)
    recall_items = enforcement.get("recalls", []) if isinstance(enforcement, dict) else []
    for item in recall_items[:5]:
        reason = _compact(item.get("reason"))
        classification = item.get("classification") or "unclassified"
        date = item.get("date") or "unknown date"
        if not reason and classification == "unclassified":
            continue
        evidence.append({
            "source": "openFDA enforcement (drug/enforcement)",
            "detail": f"Recall/enforcement record for {drug}: {classification}, initiated {date}. Reason: {reason or 'not provided'}.",
            "url": ENFORCEMENT_URL,
        })

    return evidence


@weave.op
def _critic_precedent_market(drug: str) -> list[dict]:
    """Gather independent openFDA approval evidence without reading researcher sources."""
    evidence = []

    approval_data = approvals(drug)
    applications = approval_data.get("applications", []) if isinstance(approval_data, dict) else []
    if applications:
        summaries = []
        for app in applications[:5]:
            app_no = app.get("application_number") or "unknown application"
            sponsor = app.get("sponsor") or "unknown sponsor"
            products = ", ".join(p for p in app.get("products", []) if p) or "no product names listed"
            summaries.append(f"{app_no} by {sponsor} ({products})")
        evidence.append({
            "source": "openFDA Drugs@FDA (drug/drugsfda)",
            "detail": f"Drugs@FDA applications found for {drug}: {'; '.join(summaries)}.",
            "url": DRUGSFDA_URL,
        })

    return evidence


def _classify_verdict(stance: str, claim: str, conclusion: str, evidence: list[dict]) -> str:
    text = conclusion
    has_faers = any(item.get("source") == "openFDA FAERS (drug/event)" for item in evidence)
    has_recall = any(item.get("source") == "openFDA enforcement (drug/enforcement)" for item in evidence)
    has_approval = any(item.get("source") == "openFDA Drugs@FDA (drug/drugsfda)" for item in evidence)

    if stance == "safety_efficacy":
        if has_recall and _contains_any(text, SAFETY_OPTIMISTIC_TERMS):
            return "contradicts"
        if (has_recall or has_faers) and _contains_any(text, SAFETY_RISK_TERMS):
            return "supports"
        return "silent"

    if stance == "precedent_market":
        if has_approval and _contains_any(text, NO_PRECEDENT_TERMS):
            return "contradicts"
        if has_approval and _contains_any(text, PRECEDENT_TERMS):
            return "supports"
        return "silent"

    return "silent"


@weave.op
def critic_node(state: dict) -> dict:
    drug = state.get("drug", "")
    findings = state.get("findings", [])
    contradictions = []

    for finding in findings:
        # Deliberately read only the claim-level target, not finding["evidence"] or
        # finding["fda_data"]. The critic must independently gather its own sources.
        stance = finding.get("stance", "")
        claim = finding.get("claim", "")
        conclusion = finding.get("conclusion", "")

        if stance == "safety_efficacy":
            evidence = _critic_safety_efficacy(drug)
        elif stance == "precedent_market":
            evidence = _critic_precedent_market(drug)
        else:
            evidence = []

        contradictions.append({
            "stance": stance,
            "claim": claim,
            "verdict": _classify_verdict(stance, claim, conclusion, evidence),
            "evidence": evidence,
        })

    return {"contradictions": contradictions}
