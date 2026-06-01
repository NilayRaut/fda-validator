import os, weave
import streamlit as st
from dotenv import load_dotenv
from src.graph import run_analysis
from src.confidence import _has_fda_records

# UI (BUILD_SPEC §9.8 / FR-8): drug + question → run pipeline → render the disagreement ledger
# (per-claim positions, conflict, computed-confidence badge, contradiction flag, grounding source),
# the critic's INDEPENDENT 3-lens evidence, summary metrics, and the Weave audit-trail link.
# Includes a Demo mode (sidebar) with one-click example drugs/questions for judges to try.

load_dotenv()
# Streamlit Community Cloud injects secrets via st.secrets (there is no .env there) — bridge to env
# so weave.init and the W&B Inference client (which read os.environ) work both locally and deployed.
try:
    for _k in ("WANDB_API_KEY", "WANDB_PROJECT"):
        if _k not in os.environ and _k in st.secrets:
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass
weave.init(os.environ["WANDB_PROJECT"])

WEAVE_URL = f"https://wandb.ai/{os.environ['WANDB_PROJECT']}/weave"
_BADGE = {"high": "green", "medium": "orange", "low": "red"}
_VERDICT = {"contradicts": ("🔴", "critic contradicts"),
            "supports": ("🟢", "critic supports"),
            "silent": ("⚪", "critic silent")}


def _source_counts(fda_data: dict) -> str:
    """One-line summary of how many live records each source returned, for the activity panel."""
    counts = [
        ("FAERS", len(fda_data.get("adverse_events", {}).get("top_reactions", []))),
        ("recalls", len(fda_data.get("recalls", {}).get("recalls", []))),
        ("Drugs@FDA apps", len(fda_data.get("approvals", {}).get("applications", []))),
        ("NDC products", len(fda_data.get("marketed_products", {}).get("products", []))),
        ("ClinicalTrials.gov", len(fda_data.get("clinical_trials", {}).get("trials", []))),
    ]
    hits = [f"{label}: {n}" for label, n in counts if n]
    return " · ".join(hits) if hits else "no records found"

# (label, drug, question) — curated to show the range: marketed, investigational, biologic, stimulant.
EXAMPLES = [
    ("💉 Ozempic — safety & regulatory profile", "Ozempic", "Safety and regulatory profile?"),
    ("🧬 CT041 — investigational CAR-T", "CT041", "What risks does CT041 face for marketing approval?"),
    ("💊 Humira — adverse events & biosimilar competition", "Humira",
     "Adverse-event profile and biosimilar competitive landscape?"),
    ("⚡ Adderall — safety signals & approval history", "Adderall",
     "Safety signals and regulatory approval history?"),
]

st.set_page_config(page_title="FDA Drug Regulatory Copilot", layout="wide")
st.session_state.setdefault("drug", "Ozempic")
st.session_state.setdefault("question", "Safety and regulatory profile?")
st.session_state.setdefault("autorun", False)


def _load_example(d: str, q: str):
    st.session_state.drug = d
    st.session_state.question = q
    st.session_state.autorun = True


# ---- Sidebar: demo mode + explainer ----
with st.sidebar:
    st.header("🎬 Demo mode")
    st.caption("Click an example to run it instantly — try a marketed drug, an investigational one, and more.")
    for label, d, q in EXAMPLES:
        st.button(label, on_click=_load_example, args=(d, q), use_container_width=True)
    st.divider()
    with st.expander("ℹ️ How this works"):
        st.markdown(
            "- **Two research tracks run in parallel**, grounded in live **openFDA** (marketed) and "
            "**ClinicalTrials.gov** (investigational).\n"
            "- An **independent critic** re-gathers its own evidence and critiques each claim across "
            "**nonclinical / CMC / clinical** lenses.\n"
            "- **Confidence is computed** from observable signals — never asked of the LLM.\n"
            "- If no records are found, the finding is flagged **not grounded** instead of fabricating.\n"
            "- Every step is traced in **W&B Weave** as an audit trail."
        )

# ---- Main ----
st.title("FDA Drug Regulatory Copilot")
st.caption("Two evidence-grounded research tracks plus an independent critic. We surface where the agents "
           "disagree and how confident each claim is — not one confident answer that might be wrong.")

c1, c2 = st.columns([1, 2])
drug = c1.text_input("Drug name", key="drug")
question = c2.text_input("Question", key="question")
run_clicked = st.button("Run analysis", type="primary")

if run_clicked or st.session_state.autorun:
    st.session_state.autorun = False
    drug, question = st.session_state.drug, st.session_state.question
    with st.status("Running the multi-agent pipeline…", expanded=True) as status:
        st.write("🧭 **Planner** — splitting the question into 2 parallel research tracks")
        st.write("🔬 **Researchers** — 2 tracks querying live openFDA + ClinicalTrials.gov in parallel")
        st.write("🕵️ **Critic** — independently re-gathering evidence; critiquing nonclinical / CMC / clinical")
        st.write("📊 **Disagreement engine** — computing confidence · 📝 **Synthesizer** — writing the briefing")
        out = run_analysis(drug, question)
        status.update(label="✅ Multi-agent pipeline complete", state="complete", expanded=False)

    ledger = out.get("ledger", [])
    findings = out.get("findings", [])
    findings_by_stance = {f.get("stance"): f for f in findings}
    critic_by_stance = {c.get("stance"): c for c in out.get("contradictions", [])}

    # ---- summary metrics ----
    contested = sum(1 for e in ledger if e.get("conflict") == "contradicts")
    grounded = sum(1 for f in findings if _has_fda_records(f.get("fda_data", {})))
    mean_conf = round(sum(e.get("confidence", 0) for e in ledger) / len(ledger), 2) if ledger else 0.0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Research claims", len(ledger))
    m2.metric("Grounded findings", f"{grounded}/{len(findings)}")
    m3.metric("Contested topics", contested)
    m4.metric("Mean confidence", mean_conf)

    if contested:
        st.warning(f"⚠️ {contested} topic(s) are **contested** by the critic — see the 🔴 flags below.")
    elif grounded == 0:
        st.info("ℹ️ No openFDA / ClinicalTrials.gov records were found — findings are flagged *not grounded*.")
    else:
        st.success("✅ Claims are grounded; the critic did not contradict them.")

    # ---- behind the scenes: showcase the multi-agent orchestration ----
    with st.expander("🧠 Behind the scenes — what the agents did", expanded=True):
        st.markdown("**1 · Planner** decomposed the question into 2 parallel research tracks:")
        for f in findings:
            st.markdown(f"&nbsp;&nbsp;&nbsp;• `{f.get('stance')}` → {f.get('claim')}")
        st.markdown("**2 · Researchers** (run in parallel) each pulled live records:")
        for f in findings:
            st.markdown(f"&nbsp;&nbsp;&nbsp;• **{f.get('stance')}** → {_source_counts(f.get('fda_data', {}))}")
        st.markdown("**3 · Independent critic** re-gathered its *own* evidence (it never sees the "
                    "researchers' sources) and returned a verdict per track:")
        for c in out.get("contradictions", []):
            st.markdown(f"&nbsp;&nbsp;&nbsp;• **{c.get('stance')}** → verdict **{c.get('verdict')}** "
                        f"({len(c.get('evidence', []))} independent items, incl. a nonclinical/CMC/clinical critique)")
        st.markdown("**4 · Disagreement engine** computed each confidence score deterministically "
                    "(not from the LLM). **5 · Synthesizer** wrote the briefing below.")

    st.link_button("🔍 View the full audit trail in Weave", WEAVE_URL)

    # ---- disagreement ledger ----
    st.subheader("Disagreement ledger")
    for entry in ledger:
        with st.container(border=True):
            st.markdown(f"### {entry.get('topic', '')}")
            conf = entry.get("confidence", 0.0)
            label = entry.get("confidence_label", "low")
            verdict = entry.get("conflict", "silent")
            icon, vtext = _VERDICT.get(verdict, ("⚪", verdict))

            b1, b2 = st.columns(2)
            b1.markdown(f"**Computed confidence:** :{_BADGE.get(label, 'gray')}[{label.upper()} · {conf}]")
            b2.markdown(f"**Contradiction flag:** {icon} {vtext}")
            st.progress(conf)

            for pos in entry.get("positions", []):
                stance = pos.get("stance")
                src = findings_by_stance.get(stance, {}).get("fda_data", {}).get("source", "—")
                st.markdown(f"**{stance}** — {pos.get('conclusion')}")
                st.caption(f"Grounded in: {src}")
                ev = pos.get("evidence", [])
                with st.expander(f"Researcher evidence ({len(ev)} items)"):
                    for e in ev:
                        line = f"- **{e.get('source', '')}** — {e.get('detail', '')}"
                        if e.get("url"):
                            line += f" ([source]({e['url']}))"
                        st.markdown(line)

            # The critic searched INDEPENDENTLY — its own pulls, never the researcher's evidence.
            stance = (entry.get("positions") or [{}])[0].get("stance")
            crit_ev = critic_by_stance.get(stance, {}).get("evidence", [])
            with st.expander(f"🕵️ Critic's INDEPENDENT evidence ({len(crit_ev)} items) — verdict: {verdict}"):
                if not crit_ev:
                    st.write("Critic found no independent signal for this claim.")
                for e in crit_ev:
                    # The 3-lens assessment is a multi-line block; render it titled, not as a bullet.
                    if e.get("source", "").startswith("Critic 3-lens"):
                        st.markdown(f"**{e['source']}**")
                        st.markdown(e.get("detail", ""))
                    else:
                        st.markdown(f"- **{e.get('source', '')}** — {e.get('detail', '')}")

    st.subheader("Synthesized briefing")
    st.markdown(out.get("report", ""))
