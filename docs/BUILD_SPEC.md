# BUILD SPEC — FDA Drug Regulatory Copilot

> Hand to Claude Code. Build in the order in §9, stopping at each gate so the human can verify. Every API pattern below is verified current (May 2026) — use them exactly; do not "improve" from memory. The *what* and acceptance criteria are in `REQUIREMENTS.md`; the *why* is in `PROJECT_PROPOSAL.md`.

> **⚠️ BACKEND UPDATE (2026-05-31) — supersedes Claude/web-search references below.**
> The LLM backend is now **W&B Inference** (OpenAI-compatible, model `deepseek-ai/DeepSeek-V3.1`), billed
> against `WANDB_API_KEY` — no Anthropic key. `call_claude` keeps its name and `{"text","citations"}`
> contract (see the live §4a pattern), but **W&B Inference has no web-search tool**: `use_search`/`max_uses`
> are no-ops, `citations` is always `[]`, and grounding is **openFDA-only**. Every "(+ web search …)" note
> below is therefore optional/future — researcher & critic lanes should get openFDA grounding working first,
> and only add web search later if they wire up a separate search method (see §5).
>
> **Also now built (beyond the original spec):** `src/ctgov.py` (`clinical_trials`, ClinicalTrials.gov API
> v2) grounds **investigational** compounds absent from openFDA; `openfda.drug_label` feeds the critic's
> nonclinical/clinical lenses; the critic critiques across **nonclinical / CMC / clinical**; the researcher
> emits a deterministic *not-grounded* disclaimer when no records are retrieved (no fabricated citations);
> `src/graph.py` exposes `run_analysis(drug, question)` as the single traced entry point; and
> `scripts/eval_weave.py` is a Weave Evaluation (grounding / confidence / critic / honesty).

## 1. Summary
Two specialist research tracks run in **parallel**, each grounded in **live openFDA data**, then an **adversarial critic** independently searches for contradicting evidence, a **disagreement engine** computes confidence, and a **synthesizer** surfaces conflict. Everything is traced in **Weave**. The one principle that must not break: the critic searches independently — it never reads the researchers' sources.

Tracks (label dropped — it's approval-gated):
1. **Safety & Efficacy** — FAERS adverse events + recalls (+ web search for efficacy).
2. **Precedent & Market** — Drugs@FDA approval history + NDC marketed-products (+ web search for competition).

## 2. Stack
Python 3.11+ · `openai` client → **W&B Inference** (model `deepseek-ai/DeepSeek-V3.1`, no web search) · openFDA REST + **ClinicalTrials.gov API v2** (no auth) · `langgraph>=0.6,<0.7` (Send fan-out) · `weave` (tracing + Evaluation) · `streamlit` (UI) · `requests`.

`requirements.txt`: `openai`, `weave`, `langgraph>=0.6,<0.7`, `requests`, `streamlit`, `python-dotenv`.
`.env`: `WANDB_API_KEY=...`, `WANDB_PROJECT=your-username/fda-validator`. Run `wandb login` once.

## 3. Repo structure
```
fda-validator/
├── README.md  requirements.txt  .env.example
├── main.py                      # weave.init + graph.invoke
├── app.py                       # Streamlit (last)
├── scripts/                    # proof_of_life.py, smoke_openfda.py, eval_weave.py (Weave Evaluation)
└── src/
    ├── state.py                 # contracts + reducer
    ├── llm.py                   # call_claude (W&B Inference / DeepSeek-V3.1, no search), lazy + traced
    ├── openfda.py               # deterministic FDA fetchers incl. drug_label, traced
    ├── ctgov.py                 # ClinicalTrials.gov v2 fetcher (investigational grounding), traced
    ├── confidence.py            # COMPUTED confidence (credits real records only)
    ├── disagreement.py          # builds ledger
    ├── graph.py                 # Send fan-out + wiring + run_analysis() entry point
    └── agents/
        └── planner.py  researcher.py  critic.py (3-lens)  synthesizer.py
```

## 4. Verified API patterns — USE EXACTLY

### 4a. `src/llm.py` — W&B Inference (OpenAI-compatible), no web search
```python
import os, weave, openai

# W&B Inference serves open models only (no Claude) and has NO web-search tool, so `use_search`/`max_uses`
# are accepted for interface compatibility but are NO-OPS and `citations` is always empty. The name
# `call_claude` and the {"text","citations"} contract are unchanged so no lane import breaks.
MODEL = "deepseek-ai/DeepSeek-V3.1"
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = openai.OpenAI(base_url="https://api.inference.wandb.ai/v1",
                                api_key=os.environ.get("WANDB_API_KEY"),
                                project=os.environ.get("WANDB_PROJECT"))
    return _client

@weave.op
def call_claude(system: str, user: str, use_search: bool = True, max_uses: int = 3) -> dict:
    resp = _get_client().chat.completions.create(model=MODEL, max_tokens=1500,
                                                 messages=[{"role": "system", "content": system},
                                                           {"role": "user", "content": user}])
    return {"text": resp.choices[0].message.content or "", "citations": []}
```

### 4b. `src/openfda.py` — deterministic fetchers (fail soft, always)
```python
import requests, weave
BASE = "https://api.fda.gov/drug"

def _get(endpoint, params):
    try:
        r = requests.get(f"{BASE}/{endpoint}.json", params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        return {"_error": str(e)}

@weave.op
def adverse_events(drug: str, limit: int = 5) -> dict:            # Safety & Efficacy + critic
    res = _get("event", {"search": f'patient.drug.medicinalproduct:"{drug}"',
                         "count": "patient.reaction.reactionmeddrapt.exact"})
    top = res[:limit] if isinstance(res, list) else []
    return {"drug": drug, "top_reactions": top, "source": "openFDA FAERS (drug/event)"}

@weave.op
def recalls(drug: str, limit: int = 5) -> dict:                  # Safety & Efficacy + critic
    res = _get("enforcement", {"search": f'product_description:"{drug}"', "limit": limit})
    items = [{"reason": x.get("reason_for_recall"), "classification": x.get("classification"),
              "date": x.get("recall_initiation_date")} for x in res] if isinstance(res, list) else []
    return {"drug": drug, "recalls": items, "source": "openFDA enforcement (drug/enforcement)"}

@weave.op
def approvals(drug: str, limit: int = 5) -> dict:                # Precedent & Market + critic
    res = _get("drugsfda", {"search": f'openfda.brand_name:"{drug}" openfda.generic_name:"{drug}"', "limit": limit})
    apps = [{"application_number": x.get("application_number"), "sponsor": x.get("sponsor_name"),
             "products": [p.get("brand_name") for p in x.get("products", [])]} for x in res] if isinstance(res, list) else []
    return {"drug": drug, "applications": apps, "source": "openFDA Drugs@FDA (drug/drugsfda)"}

@weave.op
def marketed_products(drug: str, limit: int = 8) -> dict:        # Precedent & Market
    res = _get("ndc", {"search": f'openfda.generic_name:"{drug}"', "limit": limit})
    items = [{"brand": x.get("brand_name"), "manufacturer": x.get("labeler_name"),
              "class": (x.get("pharm_class") or [None])[0]} for x in res] if isinstance(res, list) else []
    return {"drug": drug, "products": items, "source": "openFDA NDC (drug/ndc)"}
```

### 4c. `src/state.py` — contracts (reducer mandatory)
```python
from typing import Annotated, TypedDict
from operator import add

class Finding(TypedDict):
    stance: str            # "safety_efficacy" | "precedent_market"
    claim: str
    conclusion: str
    evidence: list[dict]   # [{source, detail, url}]
    fda_data: dict

class DisagreementEntry(TypedDict):
    topic: str
    positions: list[dict]
    conflict: str
    confidence: float
    confidence_label: str

class ResearchState(TypedDict):
    drug: str
    question: str
    claims: list[dict]
    findings: Annotated[list[Finding], add]   # parallel → REDUCER, do not remove
    contradictions: list[dict]
    ledger: list[DisagreementEntry]
    report: str
```

### 4d. `src/graph.py` — Send fan-out (2 tracks)
```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from .state import ResearchState
from .agents.planner import planner_node
from .agents.researcher import researcher_node
from .agents.critic import critic_node
from .agents.synthesizer import synthesizer_node
from .disagreement import disagreement_node

def route_to_researchers(state: ResearchState):
    return [Send("researcher", {"drug": state["drug"], "claim": c}) for c in state["claims"]]

def build_graph():
    g = StateGraph(ResearchState)
    for name, fn in [("planner", planner_node), ("researcher", researcher_node),
                     ("critic", critic_node), ("disagreement", disagreement_node),
                     ("synthesizer", synthesizer_node)]:
        g.add_node(name, fn)
    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", route_to_researchers, ["researcher"])
    g.add_edge("researcher", "critic")        # critic waits for BOTH researchers (fan-in)
    g.add_edge("critic", "disagreement")
    g.add_edge("disagreement", "synthesizer")
    g.add_edge("synthesizer", END)
    return g.compile()
```

### 4e. `src/confidence.py` — COMPUTED, not generated
```python
import weave
@weave.op
def compute_confidence(finding: dict, contradiction: dict) -> tuple[float, str]:
    score = 0.5
    score += min(len(finding.get("evidence", [])), 4) * 0.08
    if str(finding.get("fda_data", {}).get("source", "")).startswith("openFDA"):
        score += 0.15
    if "llm unavailable" in str(finding.get("conclusion", "")).lower():
        score -= 0.25
    verdict = (contradiction or {}).get("verdict", "silent")
    if verdict == "contradicts": score -= 0.35
    elif verdict == "supports":  score += 0.15
    score = max(0.0, min(1.0, score))
    return round(score, 2), ("high" if score >= 0.7 else "medium" if score >= 0.4 else "low")
```

### 4f. `main.py`
```python
import os, weave
from dotenv import load_dotenv
from src.graph import build_graph
load_dotenv(); weave.init(os.environ["WANDB_PROJECT"]); graph = build_graph()
if __name__ == "__main__":
    out = graph.invoke({"drug": "Ozempic", "question": "Safety and regulatory profile?",
                        "claims": [], "findings": [], "contradictions": [], "ledger": [], "report": ""})
    print(out["report"])
```

## 5. Agent jobs (write system prompts to match)
- **planner** (`call_claude`, no search): output a JSON array of exactly 2 claims — `[{stance:"safety_efficacy", question:...}, {stance:"precedent_market", question:...}]`. Parse defensively.
- **researcher** (parallel): branch on `claim["stance"]`. `safety_efficacy` → `adverse_events` + `recalls`; `precedent_market` → `approvals` + `marketed_products`. Then `call_claude` to write `conclusion` + `evidence` **from the openFDA data**. Return `{"findings": [Finding]}`. *(Web search for efficacy/trials/competitors is no longer available on the W&B Inference backend — get openFDA grounding working first; add web search only if a separate method is wired up.)*
- **critic** (independent): per finding, do NOT use its evidence. Independently call openFDA (`adverse_events`/`recalls` for safety; `approvals` for precedent), then classify the critic verdict from those independent sources plus the researcher's conclusion text. Append `{stance, claim, verdict ∈ {supports,contradicts,silent}, evidence}` to `contradictions`. *(Adversarial web search is unavailable on the current backend — the independent-critic principle is satisfied by querying openFDA independently; add LLM/web reasoning later only via a separate method.)*
- **disagreement_node**: zip findings with matching contradictions, call `compute_confidence`, build `DisagreementEntry` list → `ledger`.
- **synthesizer** (`call_claude`): turn `ledger` into a markdown report that presents conflict and flags low-confidence claims. Must not collapse to one verdict.

## 6. Weave = audit trail
`weave.init()` once. `@weave.op` on every node, `call_claude`, every openFDA fetcher, and `compute_confidence`. Trace shows planner → 2 parallel researchers → critic (with its independent FDA pulls) → confidence → synthesizer. Demo it as the compliance/audit record.

## 7. (interfaces) — see `REQUIREMENTS.md` §4 for the canonical contract definitions. Do not change shapes without telling the team.

## 8. Fail-soft rule
Every external call returns a typed empty default on error and the graph continues. A demo that degrades beats one that throws on stage.

## 9. BUILD ORDER — stop at each gate
1. **Scaffold + proof of life.** Repo + `requirements.txt` + `.env` + `src/llm.py`. Script: `call_claude("you are helpful","newest approaches to reducing drug adverse events")` after `weave.init` (hits W&B Inference; no web search). **GATE: answer prints + trace in W&B. Stop.**
2. **openFDA works.** `src/openfda.py`. Print `adverse_events("Ozempic")` and `approvals("Ozempic")`. **GATE: real FDA data prints, traced. Stop.**
3. **Skeleton graph.** `state.py` + `graph.py` + 5 stub nodes (incl. stub `disagreement_node`) passing dummy data end-to-end. **GATE: `python main.py` runs, full trace tree. Stop — push this so the team can build against stubs.**
4. **Fan-out live.** Real `planner` + `Send` routing. **GATE: 2 researchers appear as PARALLEL branches in Weave. Stop.**
5. **Researchers real.** Both stances calling openFDA + `call_claude`. **GATE: 2 real findings grounded in FDA data. Tag `mvp`. Stop.**
6. **Critic + confidence.** `critic.py` (independent) + `confidence.py` + `disagreement.py`. **GATE: ledger with computed confidence + contradictions. Stop.**
7. **Synthesizer.** Report presenting conflict. **GATE: end-to-end on a drug → confidence-annotated report. Stop.**
8. **Streamlit `app.py`.** Drug input → render ledger (badges, positions, contradiction flags) → Weave link. **GATE: demo-grade. Stop.**
9. **README.** Architecture, the independent-critic principle, sponsor tools (Weave), audit-trail framing.

## 10. Cut order if behind
Drop `marketed_products` enrichment first → then critic web search (openFDA-only contradiction check) → then Streamlit becomes a CLI printing report + trace URL → then synthesizer becomes a template. **Never go below 2 parallel researchers — parallelism IS the orchestration story.**

## Notes for Claude Code
- All agents use `deepseek-ai/DeepSeek-V3.1` via W&B Inference (the `MODEL` in `src/llm.py`). Don't switch models without telling the team.
- Parse all LLM JSON defensively (strip ```json fences, fall back).
- Keep `max_tokens` 1500. Web search is unavailable on this backend (`use_search`/`max_uses` are no-ops).
- Push after Step 3 so the team can clone a running stub pipeline.
