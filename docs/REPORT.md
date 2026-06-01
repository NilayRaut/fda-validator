# FDA Drug Regulatory Copilot — Project Report

A multi-agent regulatory copilot that **shows where its AI agents disagree and grounds every claim in
real data** — instead of one confident answer that might be wrong.

- **Live app:** https://fda-validator-fv6rokqkrtsnfv962ynssa.streamlit.app/
- **Public audit trail (Weave):** https://wandb.ai/fdaregulations/fda-validator/weave
- **Code:** https://github.com/NilayRaut/fda-validator
- **Result:** Top 15 at the Multi-Agent Orchestration Build Day.

> *(This file is written to double as a W&B Report — paste the sections into a Report and embed live
> Weave trace/eval panels where noted.)*

## The problem

In drug regulation a *confident wrong answer* is dangerous. Existing tools automate writing and hand back
a single polished answer with no sense of what's actually contested — so the user either trusts it blindly
or re-verifies everything by hand. And as you chain more agents, errors compound silently because a
downstream agent has no idea an upstream one made something up.

## What we built

You enter a **drug + a question**. The system runs a multi-agent pipeline (LangGraph) and returns a
briefing that *preserves disagreement* with a computed confidence per claim:

```
run_analysis(drug, question)
  → planner             splits the question into 2 research tracks
  → [ Safety & Efficacy ]   ┐  PARALLEL — grounded in live openFDA + ClinicalTrials.gov
  → [ Precedent & Market ]  ┘
  → adversarial critic   re-gathers its OWN evidence (never the researchers'); critiques across
                         NONCLINICAL / CMC / CLINICAL; returns supports | contradicts | silent
  → disagreement engine  computes per-claim confidence (deterministic, not LLM-generated)
  → synthesizer          writes a briefing that surfaces the conflict
  [ every node, model call, and data fetch traced in W&B Weave ]
```

## What makes it trustworthy (4 design choices)

1. **Parallel, grounded research.** Two tracks run concurrently, each calling deterministic fetchers:
   openFDA (FAERS, recalls, Drugs@FDA, NDC, drug labels) for **marketed** drugs and **ClinicalTrials.gov**
   for **investigational** compounds.
2. **An independent critic.** The critic never sees a researcher's evidence — it re-queries the data
   itself and challenges each claim across **nonclinical / CMC / clinical** regulatory lenses. Agents only
   add value when they bring *new* information, not when they rephrase each other.
3. **Computed confidence.** Confidence is a deterministic function of observable signals (evidence count,
   real records retrieved, critic verdict) — never a number asked of the LLM. Reproducible and explainable.
4. **No fabrication.** When no record is retrieved for a name, the finding is explicitly flagged
   *not grounded* rather than presenting the model's training-memory as evidence.

## Observability — the audit trail *is* the product

Every agent, LLM call, FDA/CT.gov query, and the confidence computation is traced in **W&B Weave**. Open a
`run_analysis` row in the [public project](https://wandb.ai/fdaregulations/fda-validator/weave) and the
full tree expands — planner → 2 parallel researchers → independent critic → confidence → synthesizer —
with inputs, outputs, and latency at every step. That tree is the compliance record.

> *In a Report: embed the Weave trace panel here.*

## Does it actually work? (Weave Evaluation)

A `weave.Evaluation` (`scripts/eval_weave.py`) scores the pipeline over marketed, investigational, and
unknown drugs:

| Scorer | Result |
|---|---|
| Findings grounded in real records | 2/3 (marketed + investigational; unknown correctly ungrounded) |
| Confidence computed & in-range | 3/3 |
| Critic verdict valid | 3/3 |
| Honest when ungrounded (no fabrication) | 3/3 |

Concrete behavior:
- **Ozempic** (marketed) → grounded in FAERS + recalls + trials; a safety topic comes back **contested** by
  the critic (low confidence) — the disagreement story, live.
- **CT041** (investigational CAR-T) → grounded in real ClinicalTrials.gov studies (phase, sponsor); the
  critic's nonclinical lens flags it honestly and notes no public CMC data.
- **Unknown name** → flagged *not grounded*, confidence held down — no invented citations.

> *In a Report: embed the Evaluation comparison panel here.*

## Tech stack

Python · LangGraph (`Send` fan-out) · W&B Weave (tracing + Evaluation) · W&B Inference
(`deepseek-ai/DeepSeek-V3.1`) · openFDA + ClinicalTrials.gov (public APIs) · Streamlit · OpenAI SDK.

## What I'd do next

- **Wire a web-search tool** for posters / press-releases / guidance (the LLM backend has none today).
- **Per-run shareable trace links** in the UI (currently links to the project).
- **Expand toward IND pre-review** (document ingestion, richer CMC grounding) — a larger scope flagged as v2.

## Reflections

Built across a multi-person team with real git friction (revert wars, stale-branch merges, a mid-flight
LLM-backend swap from Anthropic to W&B Inference). The wins that held up: **frozen interfaces** so lanes
didn't collide, **fail-soft everywhere** so a single bad API call never crashed the demo, and treating
**grounding + honesty** as first-class — which is what let the tool handle an investigational drug without
making things up. Placed top 15.
