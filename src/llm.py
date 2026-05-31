import os, weave, anthropic

# NOTE: the client is built at import time. It requires ANTHROPIC_API_KEY to be set.
# Stub agent nodes must NOT import this module (they make no Claude calls); importing it
# would make a fresh clone die at import before any work happens. Lane owners add the
# `from ..llm import call_claude` import when they implement their node.
_client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"


@weave.op
def call_claude(system: str, user: str, use_search: bool = True, max_uses: int = 3) -> dict:
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}] if use_search else []
    resp = _client.messages.create(model=MODEL, max_tokens=1500, system=system,
                                   messages=[{"role": "user", "content": user}], tools=tools)
    text, citations = "", []
    for b in resp.content:
        if b.type == "text":
            text += b.text
            for c in (getattr(b, "citations", None) or []):
                citations.append({"source": getattr(c, "title", ""), "detail": getattr(c, "cited_text", ""),
                                  "url": getattr(c, "url", "")})
    return {"text": text, "citations": citations}
