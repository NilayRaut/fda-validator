import os, weave
import streamlit as st
from dotenv import load_dotenv
from src.graph import build_graph

# LANE: UI (BUILD_SPEC §9.8 / FR-8). Drug input → run pipeline → render the disagreement
# ledger (per-claim positions, conflict, computed-confidence badge, contradiction flag),
# show the critic's INDEPENDENT evidence, and link to the Weave audit trail.

load_dotenv()
weave.init(os.environ["WANDB_PROJECT"])
graph = build_graph()

WEAVE_URL = f"https://wandb.ai/{os.environ['WANDB_PROJECT']}/weave"
_BADGE = {"high": "green", "medium": "orange", "low": "red"}
_VERDICT = {"contradicts": ("🔴", "critic contradicts"),
            "supports": ("🟢", "critic supports"),
            "silent": ("⚪", "critic silent")}

st.set_page_config(page_title="FDA Drug Regulatory Copilot", layout="wide")
st.title("FDA Drug Regulatory Copilot")
st.caption("Two openFDA-grounded research tracks plus an independent critic. We surface where the "
           "agents disagree and how confident each claim is — not one confident answer that might be wrong.")

c1, c2 = st.columns([1, 2])
drug = c1.text_input("Drug name", "Ozempic")
question = c2.text_input("Question", "Safety and regulatory profile?")

if st.button("Run analysis", type="primary"):
    with st.spinner(f"Researching {drug} across openFDA + independent critic…"):
        out = graph.invoke({"drug": drug, "question": question, "claims": [],
                            "findings": [], "contradictions": [], "ledger": [], "report": ""})

    st.link_button("🔍 View the full audit trail in Weave", WEAVE_URL)

    ledger = out.get("ledger", [])
    critic_by_stance = {c.get("stance"): c for c in out.get("contradictions", [])}

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
                st.markdown(f"**{pos.get('stance')}** — {pos.get('conclusion')}")
                ev = pos.get("evidence", [])
                with st.expander(f"Researcher evidence ({len(ev)} items)"):
                    for e in ev:
                        line = f"- **{e.get('source', '')}** — {e.get('detail', '')}"
                        if e.get("url"):
                            line += f" ([source]({e['url']}))"
                        st.markdown(line)

            # The critic searched INDEPENDENTLY — its own openFDA pulls, never the researcher's evidence.
            stance = (entry.get("positions") or [{}])[0].get("stance")
            crit_ev = critic_by_stance.get(stance, {}).get("evidence", [])
            with st.expander(f"🕵️ Critic's INDEPENDENT evidence ({len(crit_ev)} items) — verdict: {verdict}"):
                if not crit_ev:
                    st.write("Critic found no independent openFDA signal for this claim.")
                for e in crit_ev:
                    # The 3-lens assessment is a multi-line block; render it titled, not as a bullet.
                    if e.get("source", "").startswith("Critic 3-lens"):
                        st.markdown(f"**{e['source']}**")
                        st.markdown(e.get("detail", ""))
                    else:
                        st.markdown(f"- **{e.get('source', '')}** — {e.get('detail', '')}")

    st.subheader("Synthesized briefing")
    st.markdown(out.get("report", ""))
