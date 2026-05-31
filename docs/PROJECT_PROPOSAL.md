# PROJECT PROPOSAL — FDA Drug Regulatory Copilot

## The one-liner
A regulatory copilot for drugs that **shows where its AI agents disagree and grounds every claim in real FDA data** — so a professional sees which conclusions are solid, which are contested, and the evidence behind each, instead of one confident answer that might be wrong.

## The problem
In drug regulation, a confident wrong answer is dangerous. Every AI tool on the market today — Veeva, the YC-funded submission drafters — automates writing and hands you a single polished answer with no sense of what's actually contested. The user is left to either trust it blindly or re-verify everything by hand. And the more agents you chain, the more errors compound silently, because a downstream agent has no idea an upstream one made something up.

## What we're building
You enter a drug name and a question. The system runs **two specialist research tracks in parallel**, each grounded in live openFDA data:

1. **Safety & Efficacy** — clinical risk and benefit: adverse-event signals (FAERS), recalls/enforcement actions, and the efficacy picture.
2. **Precedent & Market** — regulatory context: approval history and application type from Drugs@FDA, plus the competitive landscape from the marketed-products directory.

Then the step that makes it trustworthy: an **adversarial critic independently searches openFDA for evidence that *contradicts* what the tracks concluded** — it does not re-read their sources. A **disagreement engine** scores each claim's confidence from observable signals, and a **synthesizer** presents the conflict and the evidence rather than papering over it. Every step is traced in **W&B Weave** as an audit trail of exactly how each conclusion was reached.

## Why it's different
Nobody leads with *epistemic transparency*. Existing tools optimize for speed and automation; none of them show you where the evidence is contested. That's the gap. And it's the right design for a high-stakes domain — a useful uncertain answer beats a confident wrong one.

The core principle, straight from multi-agent production research: **agents only help when they add genuinely new information, not when they rephrase each other.** That's why the critic does its own independent evidence search. It's the difference between a real validator and an expensive echo.

## Who it helps
A regulatory professional who needs to get oriented on a drug fast — understand its safety profile, its precedent, its market position — and critically, see which conclusions to trust and which to dig into, with the FDA evidence behind each. It's the fast first-pass that tells them where to look. It does not replace their legal/regulatory team; it points them at what matters.

*(Honest framing if anyone asks "who pays for this": today it's a research and orientation tool. The durable value is the architecture — agents that disagree, grounded in real data, with an audit trail. Prove it works first; argue the business model later.)*

## Why we'll place (maps to judging criteria)
- **Agent orchestration:** two specialist tracks running in parallel, fanned out at runtime, plus an adversarial critic and a synthesizer — real coordination, visible in the trace.
- **Utility:** solves a real trust problem with real FDA data, not a toy.
- **Technical execution:** clean LangGraph fan-out, deterministic openFDA grounding, computed confidence.
- **Creativity:** the transparency / self-contradiction angle nobody else has.
- **Sponsor usage:** Weave isn't bolted on — it's the audit trail, the core feature *and* the demo.

## Architecture at a glance
```
drug + question
  → planner            splits into the two tracks' questions
  → [ Safety & Efficacy ]   →   PARALLEL, each grounded in live openFDA
  → [ Precedent & Market ]  →
  → adversarial critic  independently queries openFDA for CONTRADICTING evidence
  → disagreement engine scores each claim's confidence (computed)
  → synthesizer         surfaces conflict, not a verdict
  → regulatory professional decides with evidence in hand
  [ Weave traces every step = the audit trail ]
```

## The demo
Type a drug with a contested FDA history → report renders with per-claim confidence badges and contradiction flags → cut to the Weave trace, expand the tree (planner → two parallel tracks → critic pulling real FDA data → confidence) → "this is the audit trail: exactly how every conclusion was reached." The expanding trace is the hero shot.

**Pitch line:** "Most regulatory AI gives one confident answer. Drugs are high-stakes — a confident wrong answer is dangerous. Ours shows where its agents disagree and backs every claim with real FDA data, with a full audit trail of how it got there."
