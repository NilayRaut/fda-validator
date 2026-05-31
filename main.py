import os, weave
from dotenv import load_dotenv
from src.graph import run_analysis

load_dotenv()
weave.init(os.environ["WANDB_PROJECT"])

if __name__ == "__main__":
    out = run_analysis("Ozempic", "Safety and regulatory profile?")
    print(out["report"])
