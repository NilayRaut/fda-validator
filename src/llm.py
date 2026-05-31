import os, weave, openai

# Backend: W&B Inference (OpenAI-compatible), billed against WANDB_API_KEY — no Anthropic key needed.
# W&B Inference serves open models only (model below is DeepSeek-V3.1, not Claude) and has NO web-search
# tool, so `use_search`/`max_uses` are accepted for interface compatibility but are NO-OPS and `citations`
# is always empty — grounding is openFDA-only (BUILD_SPEC §10 cut-order). The function name `call_claude`
# and its {"text", "citations"} return contract are unchanged so no lane import breaks.
#
# The client is built at import time (needs WANDB_API_KEY). Stub agent nodes must NOT import this module;
# importing it would make a fresh clone die at import. Lane owners add the import when they implement.
_client = openai.OpenAI(
    base_url="https://api.inference.wandb.ai/v1",
    api_key=os.environ.get("WANDB_API_KEY"),
    project=os.environ.get("WANDB_PROJECT"),
)
MODEL = "deepseek-ai/DeepSeek-V3.1"


@weave.op
def call_claude(system: str, user: str, use_search: bool = True, max_uses: int = 3) -> dict:
    resp = _client.chat.completions.create(model=MODEL, max_tokens=1500,
                                           messages=[{"role": "system", "content": system},
                                                     {"role": "user", "content": user}])
    return {"text": resp.choices[0].message.content or "", "citations": []}
