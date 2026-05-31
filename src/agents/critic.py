import re
import weave
from ..openfda import adverse_events, recalls, approvals, drug_label
from ..llm import call_claude

# LANE: Critic — owns critic_node.
# THE principle that must not break: the critic searches INDEPENDENTLY. It must NOT read a
# finding's evidence/fda_data. For each finding it runs its OWN openFDA queries (FAERS/recalls
# for safety; approvals for precedent) PLUS the drug label (nonclinical + clinical sections),
# then asks the LLM to critique the researcher's conclusion across three regulatory lenses —
# NONCLINICAL, CMC, and CLINICAL — grounded only in that independent evidence, and emits a
# verdict in {supports, contradicts, silent} that drives the computed confidence.

FAERS_URL = "https://open.fda.gov/apis/drug/event/"
ENFORCEMENT_URL = "https://open.fda.gov/apis/drug/enforcement/"
DRUGSFDA_URL = "https://open.fda.gov/apis/drug/drugsfda/"
LABEL_URL = "https://open.fda.gov/apis/drug/label/"

_SYSTEM = (
    "You are an adversarial FDA regulatory reviewer. You are given a researcher's claim and "
    "conclusion about a drug, plus INDEPENDENT evidence you gathered yourself from openFDA "
    "(FAERS adverse events, recalls, approvals, and the drug label's nonclinical/clinical "
    "sections). Critique the conclusion from three regulatory perspectives:\n"
    "- NONCLINICAL: animal toxicology / pharmacology signals.\n"
    "- CMC: chemistry, manufacturing & controls (impurities, stability, quality) — usually "
    "public only via recalls; if there is no public data, say so explicitly.\n"
    "- CLINICAL: efficacy, adverse events, trial evidence.\n"
    "Give 1-2 sentences per lens, grounded ONLY in the evidence provided — never invent data; "
    "if a lens has no supporting evidence, state that plainly. Finish with a final line exactly "
    "in the form 'VERDICT: supports' or 'VERDICT: contradicts' or 'VERDICT: silent', reflecting "
    "whether your independent evidence supports, contradicts, or is silent on the conclusion."
)


def _parse_verdict(text: str) -> str:
    m = re.search(r"verdict:\s*(supports|contradicts|silent)", text.lower())
    return m.group(1) if m else "silent"


def _compact(value: object, limit: int = 200) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _source_items(stance: str, fda: dict, label: dict) -> list[dict]:
    """Render the critic's INDEPENDENT raw sources into the frozen {source, detail, url} shape."""
    items = []
    if stance == "precedent_market":
        for a in fda.get("approvals", {}).get("applications", [])[:5]:
            items.append({"source": "openFDA Drugs@FDA (drug/drugsfda)",
                          "detail": f"{a.get('application_number')} — {a.get('sponsor')} — {a.get('products')}",
                          "url": DRUGSFDA_URL})
    else:
        for r in fda.get("adverse_events", {}).get("top_reactions", [])[:5]:
            items.append({"source": "openFDA FAERS (drug/event)",
                          "detail": f"{r.get('term')} — {r.get('count')} reports", "url": FAERS_URL})
        for x in fda.get("recalls", {}).get("recalls", [])[:3]:
            items.append({"source": "openFDA enforcement (drug/enforcement)",
                          "detail": f"{x.get('classification')} ({x.get('date')}): {_compact(x.get('reason'))}",
                          "url": ENFORCEMENT_URL})
    if label.get("nonclinical_toxicology"):
        items.append({"source": "openFDA Drug Label — nonclinical_toxicology",
                      "detail": _compact(label["nonclinical_toxicology"], 300), "url": LABEL_URL})
    return items


@weave.op
def critic_node(state: dict) -> dict:
    drug = state.get("drug", "")
    contradictions = []

    for finding in state.get("findings", []):
        # Read ONLY the claim-level target — never finding["evidence"] / finding["fda_data"].
        stance = finding.get("stance", "")
        claim = finding.get("claim", "")
        conclusion = finding.get("conclusion", "")

        # Independent pulls (the critic's own sources).
        label = drug_label(drug)
        if stance == "precedent_market":
            fda = {"approvals": approvals(drug)}
        else:
            fda = {"adverse_events": adverse_events(drug), "recalls": recalls(drug)}

        grounding = {
            "openFDA": fda,
            "label_nonclinical_toxicology": label.get("nonclinical_toxicology", ""),
            "label_clinical_pharmacology": label.get("clinical_pharmacology", ""),
            "label_clinical_studies": label.get("clinical_studies", ""),
            "label_warnings": label.get("warnings", ""),
        }
        user = (f"Drug: {drug}\nResearcher claim: {claim}\nResearcher conclusion: {conclusion}\n\n"
                f"Your independent evidence:\n{grounding}\n\n"
                "Critique across NONCLINICAL, CMC, and CLINICAL, then give your VERDICT.")
        try:  # fail-soft (BUILD_SPEC §8): degrade rather than crash the graph
            critique = call_claude(_SYSTEM, user, use_search=False).get("text", "")
        except Exception as e:
            critique = f"[critic LLM unavailable: {e}]"

        evidence = [{"source": "Critic 3-lens assessment (nonclinical / CMC / clinical)",
                     "detail": critique, "url": ""}]
        evidence += _source_items(stance, fda, label)

        contradictions.append({
            "stance": stance,
            "claim": claim,
            "verdict": _parse_verdict(critique),
            "evidence": evidence,
        })

    return {"contradictions": contradictions}
