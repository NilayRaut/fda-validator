import os, weave
import streamlit as st
from dotenv import load_dotenv
from src.graph import build_graph

# LANE: UI — built LAST (BUILD_SPEC §9.8). This is a minimal placeholder: drug input →
# run → dump report. TODO(ui): render the ledger (per-claim positions, conflict, confidence
# badge, contradiction flag) and link to the run's Weave trace.

load_dotenv()
weave.init(os.environ["WANDB_PROJECT"])
graph = build_graph()

st.title("FDA Drug Regulatory Copilot")
drug = st.text_input("Drug name", "Ozempic")

if st.button("Run analysis"):
    out = graph.invoke({"drug": drug, "question": "Safety and regulatory profile?",
                        "claims": [], "findings": [], "contradictions": [], "ledger": [], "report": ""})
    st.markdown(out["report"])
    st.json(out["ledger"])
