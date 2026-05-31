import os, weave
from dotenv import load_dotenv
from src.graph import build_graph

load_dotenv()
weave.init(os.environ["WANDB_PROJECT"])
graph = build_graph()

if __name__ == "__main__":
    out = graph.invoke({"drug": "Ozempic", "question": "Safety and regulatory profile?",
                        "claims": [], "findings": [], "contradictions": [], "ledger": [], "report": ""})
    print(out["report"])
