import os, weave, openai

# Backend: W&B Inference (OpenAI-compatible), billed against WANDB_API_KEY — no Anthropic key needed.
# W&B Inference serves open models only (model below is DeepSeek-V3.1, not Claude) and has NO web-search
# tool, so `use_search`/`max_uses` are accepted for interface compatibility but are NO-OPS and `citations`
# is always empty — grounding is openFDA-only (BUILD_SPEC §10 cut-order). The function name `call_claude`
# and its {"text", "citations"} return contract are unchanged so no lane import breaks.
#
# The client is built LAZILY on first call (not at import) so import order doesn't matter — the entry
# point can `load_dotenv()` before any LLM call happens — and a keyless clone can still import this module.
MODEL = "deepseek-ai/DeepSeek-V3.1"
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = openai.OpenAI(base_url="https://api.inference.wandb.ai/v1",
                                api_key=os.environ.get("WANDB_API_KEY"),
                                project=os.environ.get("WANDB_PROJECT"))
    return _client


@weave.op
def call_claude(system: str, user: str, use_search: bool = True, max_uses: int = 3) -> dict:
    resp = _get_client().chat.completions.create(model=MODEL, max_tokens=1500,
                                                 messages=[{"role": "system", "content": system},
                                                           {"role": "user", "content": user}])
    return {"text": resp.choices[0].message.content or "", "citations": []}
