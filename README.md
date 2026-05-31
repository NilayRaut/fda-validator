# FDA Drug Regulatory Copilot

A regulatory copilot for drugs that **shows where its AI agents disagree and grounds every claim in
real FDA data** — so a professional sees which conclusions are solid, which are contested, and the
evidence behind each, instead of one confident answer that might be wrong.

**Live demo:** https://fda-validator-fv6rokqkrtsnfv962ynssa.streamlit.app/

You enter a drug name and a question. Two specialist research tracks run **in parallel**, each grounded
in live public data. An **independent adversarial critic** then gathers its *own* evidence — it never
reads the researchers' sources — and critiques each claim across **nonclinical, CMC, and clinical**
regulatory lenses. A deterministic **disagreement engine** computes a confidence score from observable
signals (never from the LLM), and a **synthesizer** writes a briefing that *surfaces* the conflict
instead of papering over it. Every step is traced in **W&B Weave** as an audit trail.

```
drug + question
  → planner             splits the work into two research questions
  → [ Safety & Efficacy ]   ┐  PARALLEL — each grounded in live openFDA + ClinicalTrials.gov
  → [ Precedent & Market ]  ┘
  → adversarial critic   independently re-queries the data; critiques across
                         NONCLINICAL / CMC / CLINICAL; emits supports|contradicts|silent
  → disagreement engine  computes per-claim confidence (deterministic, not LLM-generated)
  → synthesizer          writes a briefing that preserves the disagreement
  [ W&B Weave traces every node, model call, and data fetch = the audit trail ]
```

## Why it's different

Most regulatory AI gives one polished, confident answer — dangerous in a domain where a confident
*wrong* answer costs lives. This tool leads with **epistemic transparency**: it shows which conclusions
are contested and backs every claim with real evidence, and it **refuses to fabricate** — for an
investigational compound absent from the databases, it says so plainly rather than inventing citations.

## How it grounds claims

| Source | API | Used for |
|---|---|---|
| **openFDA FAERS** (`drug/event`) | public, no auth | adverse-event signals (marketed) |
| **openFDA enforcement** (`drug/enforcement`) | public, no auth | recalls (marketed) |
| **openFDA Drugs@FDA** (`drug/drugsfda`) | public, no auth | approval history (marketed) |
| **openFDA NDC** (`drug/ndc`) | public, no auth | marketed products / competitors |
| **openFDA Drug Label** (`drug/label`) | public, no auth | nonclinical / clinical label sections (critic) |
| **ClinicalTrials.gov** (API v2) | public, no auth | **investigational** compounds (phase, status, sponsor) |

openFDA covers *marketed* products; **ClinicalTrials.gov** grounds *investigational* compounds that
aren't in openFDA yet. If neither returns records for a name, the finding is explicitly flagged as **not
grounded** (a deterministic disclaimer, so the model can't pass off training-memory citations as evidence).

The **LLM backend is W&B Inference** (OpenAI-compatible, model `deepseek-ai/DeepSeek-V3.1`) — billed
against your `WANDB_API_KEY`, no separate Anthropic key. It has no built-in web search, so grounding
comes entirely from the deterministic data fetchers above (not from the model's memory).

## Setup

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # project-local venv
cp .env.example .env        # fill WANDB_API_KEY and WANDB_PROJECT
.venv/bin/wandb login       # once
```

`.env`:
```
WANDB_API_KEY=...                       # from https://wandb.ai/authorize
WANDB_PROJECT=your-entity/fda-validator # entity/project; weave.init reads it (required)
```

> **Note:** install into a **project-local `.venv`**, not a shared conda env — this project needs
> `langgraph>=1.2`, which can conflict with older langgraph pinned elsewhere.

## Run

```bash
.venv/bin/python main.py                  # end-to-end pipeline on Ozempic → prints the briefing
.venv/bin/streamlit run app.py            # the interactive UI (ledger, badges, critic, Weave link)
.venv/bin/python scripts/eval_weave.py    # Weave Evaluation: grounding / confidence / critic / honesty
.venv/bin/python scripts/proof_of_life.py # gate: one W&B Inference call
.venv/bin/python scripts/smoke_openfda.py # gate: real openFDA data (no LLM key needed)
```

Try a **marketed** drug (`Ozempic`), an **investigational** code (`CT041`), and a nonsense name to see
the grounding, confidence, and honesty behavior change.

## Deploy (Streamlit Community Cloud)

The app is deployed at the link above. To deploy your own:
1. Push to GitHub, then at **share.streamlit.io** → New app → this repo, branch `main`, file `app.py`.
2. **Advanced settings → Secrets** (TOML):
   ```toml
   WANDB_API_KEY = "your-key"
   WANDB_PROJECT = "your-entity/fda-validator"
   ```
   `app.py` bridges `st.secrets` → environment automatically, so no `.env` is needed in the cloud.
3. Deploy → you get a public `*.streamlit.app` URL. Note: every visitor run spends your W&B Inference credits.

## The Weave audit trail (the demo hero shot)

Open the project in W&B Weave. The trace list shows run **roots** named **`run_analysis`** (the columns
there are the *initial* inputs, so `findings`/`ledger` look empty — that's expected). **Click a
`run_analysis` row** to expand the full tree:

```
run_analysis (drug, question)
 └─ LangGraph
     ├─ planner          → 2 claims
     ├─ researcher  ┐ parallel, each with its openFDA + ClinicalTrials.gov fetches + call_claude
     ├─ researcher  ┘
     ├─ critic           → independent fetches + 3-lens critique + verdict
     ├─ disagreement     → compute_confidence (deterministic)
     └─ synthesizer      → briefing
```

Every model call, FDA query, and the confidence computation is captured with inputs/outputs/latency —
that tree *is* the compliance record.

## Components

| Component | File | Role |
|---|---|---|
| Planner | `src/agents/planner.py` | drug + question → 2 research claims (defensive JSON parse) |
| Researchers (×2, parallel) | `src/agents/researcher.py` | openFDA + ClinicalTrials.gov grounding → a `Finding` each |
| Adversarial critic | `src/agents/critic.py` | independent re-query + nonclinical/CMC/clinical critique + verdict |
| Disagreement + confidence | `src/disagreement.py`, `src/confidence.py` | deterministic per-claim confidence ledger |
| Synthesizer | `src/agents/synthesizer.py` | conflict-preserving briefing |
| Data fetchers | `src/openfda.py`, `src/ctgov.py` | deterministic, fail-soft, Weave-traced |
| LLM client | `src/llm.py` | W&B Inference (DeepSeek-V3.1), lazy-built |
| Graph wiring | `src/graph.py` | LangGraph `Send` fan-out + `run_analysis` entry point |
| UI | `app.py` | Streamlit: input → ledger → critic evidence → Weave link |

## Invariants (do not break)

- **The critic searches independently** — never pass it a researcher's `evidence`/`fda_data`; it runs
  its own openFDA + label queries. This is the whole point.
- **Confidence is computed, not generated** — `compute_confidence` is deterministic; never ask the LLM
  for a confidence number. It credits grounding only when a real record was actually retrieved.
- **Never fabricate** — when no record is retrieved, the finding is flagged *not grounded* rather than
  presenting model-memory citations as evidence.
- **Fail soft** — every external call returns a typed empty default on error; the graph never crashes.
- **Model** is `deepseek-ai/DeepSeek-V3.1` via W&B Inference; `max_tokens` ≤ 1500; no web search.
- **`src/llm.py` stays import-safe** — the client is built lazily, so a keyless clone can import it.

## Docs

Deeper context in [`docs/`](docs/): `PROJECT_PROPOSAL.md` (why), `REQUIREMENTS.md` (what + frozen
interface contracts), `BUILD_SPEC.md` (how + build order).
