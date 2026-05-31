# FDA Drug Regulatory Copilot

A regulatory copilot for drugs that **shows where its AI agents disagree and grounds every claim in
real FDA data** — so a professional sees which conclusions are solid, which are contested, and the
evidence behind each, instead of one confident answer that might be wrong.

Two specialist research tracks run **in parallel**, each grounded in live **openFDA** data. Then an
**adversarial critic** independently searches for *contradicting* evidence (it never reads the
researchers' sources), a **disagreement engine** computes confidence from observable signals, and a
**synthesizer** presents the conflict rather than resolving it. Every step is traced in **W&B Weave**
as the audit trail.

```
drug + question
  → planner            splits into the two tracks' questions
  → [ Safety & Efficacy ]   →   PARALLEL, each grounded in live openFDA
  → [ Precedent & Market ]  →
  → adversarial critic  independently queries openFDA for CONTRADICTING evidence
  → disagreement engine scores each claim's confidence (computed, not LLM-generated)
  → synthesizer         surfaces conflict, not a verdict
  [ Weave traces every step = the audit trail ]
```

Full context in [`docs/`](docs/): `PROJECT_PROPOSAL.md` (why), `REQUIREMENTS.md` (what + interfaces),
`BUILD_SPEC.md` (how + build order).

## Status: stub scaffold (BUILD_SPEC §9 steps 1–3)

The shared foundation is **real** (`llm.py`, `openfda.py`, `state.py`, `confidence.py`, `graph.py`).
The agent nodes are **stubs** that return shape-correct dummy data so the graph runs end-to-end
today. Each lane owner replaces exactly one stubbed function against the frozen interfaces.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # fill ANTHROPIC_API_KEY and WANDB_PROJECT
wandb login                 # once
```

`WANDB_PROJECT` is **required** before the first run — `weave.init` reads it, and `main.py` will fail
fast with a clear `KeyError` if it's unset. `ANTHROPIC_API_KEY` is required only once you implement a
node that calls Claude (the stubs make no Claude calls).

## Run

```bash
python main.py                      # end-to-end stub pipeline → prints report, full Weave trace tree
python scripts/proof_of_life.py     # §9.1 gate: one Claude call + web search (needs ANTHROPIC_API_KEY)
python scripts/smoke_openfda.py     # §9.2 gate: real FAERS + Drugs@FDA data (no Anthropic key)
streamlit run app.py                # UI placeholder (built out last)
```

## Lanes — who owns what

Interfaces are **frozen** (see [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) §4 and the header in
[`src/state.py`](src/state.py)). **Ping the team before changing any shape** — it breaks other lanes.
Fill your stub, then rerun `python main.py` to confirm the graph still runs.

| Lane | Owns (file / function) | Depends on | Gate |
|---|---|---|---|
| Foundation (shared, done) | `src/llm.py`, `src/openfda.py`, `src/state.py`, `src/graph.py`, `src/confidence.py`, `main.py` | — | §9.1–3 |
| Planner | `src/agents/planner.py` → `planner_node` | `state.py` | §9.4 |
| Researcher: Safety & Efficacy | `src/agents/researcher.py` → `_research_safety_efficacy` | `openfda.py`, `llm.py` | §9.5 |
| Researcher: Precedent & Market | `src/agents/researcher.py` → `_research_precedent_market` | `openfda.py`, `llm.py` | §9.5 |
| Critic | `src/agents/critic.py` → `critic_node` | `openfda.py`, `llm.py` | §9.6 |
| Disagreement + Confidence | `src/disagreement.py`, tune `src/confidence.py` | `state.py` | §9.6 |
| Synthesizer | `src/agents/synthesizer.py` → `synthesizer_node` | `state.py` | §9.7 |
| UI | `app.py` | `graph.py` | §9.8 |

The two researcher tracks share `researcher.py` but each owns a separate helper function, so they
don't edit the same lines.

### Rules that must not break
- **The critic searches independently** — it must NOT be passed a researcher's `evidence`/`fda_data`.
  It runs its own openFDA queries and adversarial web searches. This is the whole point.
- **Confidence is computed, not generated** — `compute_confidence` is deterministic; never ask the LLM
  for a confidence number.
- **Fail soft** — every external call returns a typed empty default on error; the graph never crashes.
- **Model is `claude-sonnet-4-6`**, `max_tokens` ≤ 1500, web `max_uses` ≤ 3.
- **Stub nodes must not import `src/llm.py`** — it builds the Anthropic client at import time, which
  would break a keyless clone. Add the import when you implement your node.
