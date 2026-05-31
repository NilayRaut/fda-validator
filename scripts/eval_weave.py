"""W&B Weave Evaluation for the FDA Drug Regulatory Copilot.

Runs the full pipeline over a small drug set and scores it on the properties that matter for a
trustworthy regulatory tool — grounding, computed confidence, critic verdicts, and honesty when
no data exists. Results (per-row + aggregate) land in Weave alongside the run traces.

Run from the repo root:  .venv/bin/python scripts/eval_weave.py
Needs WANDB_API_KEY + WANDB_PROJECT in .env (same as the app).
"""
import asyncio
import os
import sys

import weave
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()
weave.init(os.environ["WANDB_PROJECT"])

from src.confidence import _has_fda_records
from src.graph import run_analysis

# Marketed (should ground in openFDA), investigational (should ground in ClinicalTrials.gov),
# and an unknown name (should ground in NOTHING → honesty disclaimer + low confidence).
DATASET = [
    {"drug": "Ozempic", "question": "Safety and regulatory profile?", "expect": "marketed"},
    {"drug": "CT041", "question": "What risks does CT041 face for marketing approval?", "expect": "investigational"},
    {"drug": "Zzqlptxn", "question": "Safety and regulatory profile?", "expect": "no_data"},
]


@weave.op
def model(drug: str, question: str) -> dict:
    return run_analysis(drug, question)


@weave.op
def grounding_score(output: dict) -> dict:
    findings = output.get("findings", [])
    grounded = sum(1 for f in findings if _has_fda_records(f.get("fda_data", {})))
    return {"grounded_findings": grounded,
            "fully_grounded": bool(findings) and grounded == len(findings)}


@weave.op
def confidence_score(output: dict) -> dict:
    ledger = output.get("ledger", [])
    valid = all(
        isinstance(e.get("confidence"), (int, float)) and 0.0 <= e["confidence"] <= 1.0
        and e.get("confidence_label") in {"low", "medium", "high"}
        for e in ledger
    )
    return {"has_ledger": bool(ledger), "confidence_valid": bool(ledger) and valid}


@weave.op
def critic_score(output: dict) -> dict:
    cs = output.get("contradictions", [])
    valid = all(c.get("verdict") in {"supports", "contradicts", "silent"} for c in cs)
    return {"critic_verdicts_valid": bool(cs) and valid}


@weave.op
def honesty_score(expect: str, output: dict) -> dict:
    # When nothing was retrieved, every finding must carry the "not grounded" disclaimer
    # (no fabricated citations passed off as evidence).
    findings = output.get("findings", [])
    ungrounded = [f for f in findings if not _has_fda_records(f.get("fda_data", {}))]
    disclaimer_ok = all("not grounded" in f.get("conclusion", "").lower() for f in ungrounded)
    return {"no_data_case": expect == "no_data",
            "honest_when_ungrounded": disclaimer_ok}


if __name__ == "__main__":
    evaluation = weave.Evaluation(
        name="fda-validator-quality",
        dataset=DATASET,
        scorers=[grounding_score, confidence_score, critic_score, honesty_score],
    )
    asyncio.run(evaluation.evaluate(model))
    print("Evaluation complete — open the Weave project to see per-row scores and the aggregate.")
