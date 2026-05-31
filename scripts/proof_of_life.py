"""BUILD_SPEC §9.1 gate: answer prints AND a trace appears in W&B.
Run: python scripts/proof_of_life.py  (needs WANDB_API_KEY, WANDB_PROJECT + wandb login)."""
import os, sys, weave
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()
weave.init(os.environ["WANDB_PROJECT"])

from src.llm import call_claude

out = call_claude("you are helpful", "newest approaches to reducing drug adverse events")
print(out["text"])
print("\ncitations:", out["citations"])
