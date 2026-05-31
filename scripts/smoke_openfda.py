"""BUILD_SPEC §9.2 gate: real FDA data prints, traced.
Run: python scripts/smoke_openfda.py  (needs wandb login; no Anthropic key required)."""
import os, sys, weave
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()
weave.init(os.environ["WANDB_PROJECT"])

from src.openfda import adverse_events, approvals

print("adverse_events('Ozempic'):", adverse_events("Ozempic"))
print("\napprovals('Ozempic'):", approvals("Ozempic"))
